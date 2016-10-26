import datetime
import json
from decimal import Decimal
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.db.models.aggregates import Min, Max
from django_rq.decorators import job

from tunga.settings import BITPESA_SENDER
from tunga_profiles.models import ClientNumber
from tunga_tasks.models import ProgressEvent, Task, ParticipantPayment, \
    TaskInvoice
from tunga_utils import bitcoin_utils, coinbase_utils, bitpesa
from tunga_utils.constants import CURRENCY_BTC, PAYMENT_METHOD_BTC_WALLET, \
    PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_MOBILE_MONEY, UPDATE_SCHEDULE_HOURLY, UPDATE_SCHEDULE_DAILY, \
    UPDATE_SCHEDULE_WEEKLY, UPDATE_SCHEDULE_MONTHLY, UPDATE_SCHEDULE_QUATERLY, UPDATE_SCHEDULE_ANNUALLY, \
    PROGRESS_EVENT_TYPE_PERIODIC, PROGRESS_EVENT_TYPE_SUBMIT, PAYMENT_STATUS_PENDING, PAYMENT_STATUS_PROCESSING, \
    PAYMENT_STATUS_INITIATED
from tunga_utils.helpers import clean_instance


@job
def initialize_task_progress_events(task):
    task = clean_instance(task, Task)
    update_task_submit_milestone(task)
    update_task_periodic_updates(task)


@job
def update_task_submit_milestone(task):
    task = clean_instance(task, Task)
    if task.deadline:
        days_before = task.fee > 150 and 2 or 1
        submission_date = task.deadline - datetime.timedelta(days=days_before)
        defaults = {'due_at': submission_date, 'title': 'Submit final draft'}
        ProgressEvent.objects.update_or_create(task=task, type=PROGRESS_EVENT_TYPE_SUBMIT, defaults=defaults)


@job
def update_task_periodic_updates(task):
    task = clean_instance(task, Task)
    if task.update_interval and task.update_interval_units:
        periodic_start_date = task.progressevent_set.filter(
            task=task, type=PROGRESS_EVENT_TYPE_PERIODIC
        ).aggregate(latest_date=Max('due_at'))['latest_date']

        now = datetime.datetime.utcnow()
        if periodic_start_date and periodic_start_date > now:
            return

        if not periodic_start_date:
            periodic_start_date = task.participation_set.filter(
                task=task, accepted=True
            ).aggregate(start_date=Min('activated_at'))['start_date']

        if periodic_start_date:
            period_map = {
                UPDATE_SCHEDULE_HOURLY: 'hours',
                UPDATE_SCHEDULE_DAILY: 'days',
                UPDATE_SCHEDULE_WEEKLY: 'weeks',
                UPDATE_SCHEDULE_MONTHLY: 'months',
                UPDATE_SCHEDULE_QUATERLY: {'months': 3},
                UPDATE_SCHEDULE_ANNUALLY: 'years'
            }
            period_info = period_map.get(task.update_interval_units, None)
            if period_info:
                unit = isinstance(period_info, dict) and period_info.keys()[0] or period_info
                multiplier = isinstance(period_info, dict) and period_info.values()[0] or 1
                delta = {unit: multiplier * task.update_interval_units}
                last_update_at = periodic_start_date
                while True:
                    next_update_at = last_update_at + relativedelta(**delta)
                    if not task.deadline or next_update_at < task.deadline:
                        ProgressEvent.objects.update_or_create(
                            task=task, type=PROGRESS_EVENT_TYPE_PERIODIC, due_at=next_update_at
                        )
                    if next_update_at > now:
                        break
                    else:
                        last_update_at = next_update_at


@job
def distribute_task_payment(task):
    task = clean_instance(task, Task)
    if not task.paid:
        return

    if task.pay_distributed:
        return

    pay_description = task.summary

    participation_shares = task.get_payment_shares()
    payments = task.taskpayment_set.filter(received_at__isnull=False, processed=False)
    task_distribution = []
    for payment in payments:
        portion_distribution = []
        for item in participation_shares:
            participant = item['participant']
            share = item['share']
            portion_sent = False

            if not participant.user:
                continue

            participant_pay, created = ParticipantPayment.objects.get_or_create(
                source=payment, participant=participant
            )
            payment_method = participant.user.payment_method
            if created or (participant_pay and participant_pay.status == PAYMENT_STATUS_PENDING):
                if payment_method in [PAYMENT_METHOD_BTC_ADDRESS, PAYMENT_METHOD_BTC_WALLET]:
                    if not (participant_pay.destination and bitcoin_utils.is_valid_btc_address(participant_pay.destination)):
                        participant_pay.destination = participant.user.btc_address
                    transaction = send_payment_share(
                        destination=participant_pay.destination,
                        amount=Decimal(share)*payment.btc_received,
                        idem=str(participant_pay.idem_key),
                        description='%s - %s' % (pay_description, participant.user.display_name)
                    )
                    if transaction.status not in [
                        coinbase_utils.TRANSACTION_STATUS_FAILED, coinbase_utils.TRANSACTION_STATUS_EXPIRED,
                        coinbase_utils.TRANSACTION_STATUS_CANCELED
                    ]:
                        participant_pay.ref = transaction.id
                        participant_pay.btc_sent = abs(Decimal(transaction.amount.amount))
                        participant_pay.status = PAYMENT_STATUS_PROCESSING
                        participant_pay.save()
                        portion_sent = True
                elif payment_method == PAYMENT_METHOD_MOBILE_MONEY:
                    share_amount = Decimal(share)*payment.btc_received
                    recipients = [
                        {
                            bitpesa.KEY_REQUESTED_AMOUNT: float(
                                bitcoin_utils.get_valid_btc_amount(share_amount)
                            ),
                            bitpesa.KEY_REQUESTED_CURRENCY: CURRENCY_BTC,
                            bitpesa.KEY_PAYOUT_METHOD: {
                                bitpesa.KEY_TYPE: bitpesa.get_pay_out_method(participant.user.mobile_money_cc),
                                bitpesa.KEY_DETAILS: {
                                    bitpesa.KEY_FIRST_NAME: participant.user.first_name,
                                    bitpesa.KEY_LAST_NAME: participant.user.last_name,
                                    bitpesa.KEY_PHONE_NUMBER: participant.user.mobile_money_number
                                }
                            }
                        }
                    ]
                    bitpesa_nonce = str(uuid4())
                    transaction = bitpesa.create_transaction(
                        BITPESA_SENDER, recipients, input_currency=CURRENCY_BTC,
                        transaction_id=participant_pay.id, nonce=bitpesa_nonce
                    )
                    if transaction:
                        participant_pay.ref = transaction.get(bitpesa.KEY_ID, None)
                        participant_pay.status = PAYMENT_STATUS_INITIATED
                        participant_pay.extra = bitpesa_nonce
                        participant_pay.save()

                        if complete_bitpesa_payment(transaction):
                            portion_sent = True
            elif participant_pay and payment_method == PAYMENT_METHOD_MOBILE_MONEY and \
                            participant_pay.status == PAYMENT_STATUS_INITIATED:
                transaction_details = bitpesa.call_api(
                    bitpesa.get_endpoint_url('transactions/%s' % participant_pay.ref),
                    'GET', str(uuid4()), data={}
                )
                transaction = transaction_details.json().get(bitpesa.KEY_OBJECT)
                if transaction and complete_bitpesa_payment(transaction):
                    portion_sent = True

            portion_distribution.append(portion_sent)
        if portion_distribution and False not in portion_distribution:
            payment.processed = True
            payment.save()
            task_distribution.append(True)
        else:
            task_distribution.append(False)
    if task_distribution and False not in task_distribution:
        task.pay_distributed = True
        task.save()


def complete_bitpesa_payment(transaction):
    bp_transaction_id = transaction.get(bitpesa.KEY_ID, None)
    metadata = transaction.get(bitpesa.KEY_METADATA, None)
    reference = metadata.get(bitpesa.KEY_REFERENCE, None)
    bp_idem_key = metadata.get(bitpesa.KEY_IDEM_KEY, None)

    input_amount = transaction.get(bitpesa.KEY_INPUT_AMOUNT, 0)
    payin_methods = transaction.get(bitpesa.KEY_PAYIN_METHODS, None)

    destination_address = None
    if payin_methods:
        out_details = payin_methods[0][bitpesa.KEY_OUT_DETAILS]
        # Key was originally 'bitcoin_address' on first test but it appeared to have 'Address',
        # Check both for redundancy and inquire from BitPesa on this
        if bitpesa.KEY_BITCOIN_ADDRESS in out_details:
            destination_address = out_details.get(bitpesa.KEY_BITCOIN_ADDRESS, None)
        else:
            destination_address = out_details.get("Address", None)
        if not destination_address:
            destination_address = payin_methods[0][bitpesa.KEY_IN_DETAILS].get(bitpesa.KEY_ADDRESS, None)

    if destination_address:
        try:
            payment = ParticipantPayment.objects.get(
                id=reference, ref=bp_transaction_id, extra=bp_idem_key, status=PAYMENT_STATUS_INITIATED
            )
        except:
            payment = None

        if payment:
            share_amount = Decimal(
                bitcoin_utils.get_valid_btc_amount(
                    payment.source.btc_received * Decimal(payment.participant.payment_share)
                )
            )

            if input_amount <= share_amount:
                cb_transaction = send_payment_share(
                    destination=destination_address,
                    amount=input_amount,
                    idem=str(payment.idem_key),
                    description='%s - %s' % (
                        payment.participant.task.summary, payment.participant.user.display_name
                    )
                )
                if cb_transaction.status not in [
                    coinbase_utils.TRANSACTION_STATUS_FAILED, coinbase_utils.TRANSACTION_STATUS_EXPIRED,
                    coinbase_utils.TRANSACTION_STATUS_CANCELED
                ]:
                    payment.btc_sent = input_amount
                    payment.destination = destination_address
                    payment.ref = cb_transaction.id
                    payment.status = PAYMENT_STATUS_PROCESSING
                    payment.extra = json.dumps(dict(bitpesa=bp_transaction_id))
                    payment.save()
                    return True
    return False


def send_payment_share(destination, amount, idem, description=None):
    client = coinbase_utils.get_api_client()
    account = client.get_primary_account()
    transaction = account.send_money(
        to=destination,
        amount=bitcoin_utils.get_valid_btc_amount(amount),
        currency=CURRENCY_BTC,
        idem=idem,
        description=description
    )
    return transaction


@job
def generate_invoice_number(invoice):
    invoice = clean_instance(invoice, TaskInvoice)
    if not invoice.number:
        client, created = ClientNumber.objects.get_or_create(user=invoice.client)
        client_number = client.number
        task_number = invoice.task.task_number
        previous_for_month = TaskInvoice.objects.filter(
            created_at__year=invoice.created_at.year,
            created_at__month=invoice.created_at.month,
            created_at__lt=invoice.created_at
        ).count()

        month_number = previous_for_month + 1
        invoice_number = '%s%s%s%s' % (
            client_number, invoice.created_at.strftime('%Y%m'), '{:02d}'.format(month_number), task_number
        )
        invoice.number = invoice_number
        invoice.save()
    return invoice
