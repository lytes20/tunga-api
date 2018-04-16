import base64
from ConfigParser import NoOptionError

from exactonline.api import ExactApi
from exactonline.exceptions import ObjectDoesNotExist
from exactonline.resource import POST
from exactonline.storage import ExactOnlineConfig

from tunga.settings import EXACT_DOCUMENT_TYPE_PURCHASE_INVOICE, EXACT_DOCUMENT_TYPE_SALES_INVOICE, \
    EXACT_JOURNAL_CLIENT_SALES, EXACT_JOURNAL_DEVELOPER_SALES, EXACT_JOURNAL_DEVELOPER_PURCHASE, \
    EXACT_PAYMENT_CONDITION_CODE_14_DAYS, EXACT_VAT_CODE_NL, EXACT_VAT_CODE_WORLD, EXACT_GL_ACCOUNT_CLIENT_FEE, \
    EXACT_GL_ACCOUNT_DEVELOPER_FEE, EXACT_GL_ACCOUNT_TUNGA_FEE, EXACT_VAT_CODE_EUROPE
from tunga_utils.constants import CURRENCY_EUR, VAT_LOCATION_NL, VAT_LOCATION_EUROPE
from tunga_utils.models import SiteMeta


class ExactStorage(ExactOnlineConfig):

    def get_meta_key(self, section, option):
        return 'exact.{}.{}'.format(section, option)

    def get(self, section, option):
        try:
            return SiteMeta.objects.get(meta_key=self.get_meta_key(section, option)).meta_value
        except:
            raise NoOptionError()

    def set(self, section, option, value):
        SiteMeta.objects.update_or_create(meta_key=self.get_meta_key(section, option), defaults=dict(meta_value=value))


def get_api():
    storage = ExactStorage()
    return ExactApi(storage=storage)


def upload_invoice(task, user, invoice_type, invoice_file, amount, vat_location=None):
    """
    :param task: parent task for the invoice
    :param user: Tunga user related to the invoice e.g a client or a developer
    :param invoice_type: type of invoice e.g 'client', 'developer', 'tunga'
    :param invoice_file: generated file object for the invoice
    :param amount:
    :param vat_location: NL, europe or world
    :return:
    """
    exact_api = get_api()
    invoice = task.invoice

    if invoice_type == 'type' and invoice.version == 1:
        # Developer (tunga invoicing dev) invoices are only part of the old invoice scheme
        return

    exact_user_id = None
    try:
        exact_user_id = exact_api.relations.get(relation_code=user.exact_code)['ID']
    except (ObjectDoesNotExist, TypeError):
        pass

    relation_dict = dict(
        Code=user.exact_code,
        Name=user.display_name,
        Email=user.email,
        City=user.profile and user.profile.city_name or '',
        Country=user.profile and user.profile.country.code or '',
    )

    if invoice_type in ['client', 'developer']:
        relation_dict['Status'] = 'C'  # Is customer with no status

    relation_dict['IsSales'] = False
    relation_dict['IsSupplier'] = bool(invoice_type != 'client')

    if exact_user_id:
        exact_api.relations.update(exact_user_id, relation_dict)
    else:
        exact_user = exact_api.relations.create(relation_dict)
        exact_user_id = exact_user['ID']

    invoice_number = invoice.invoice_id(invoice_type=invoice_type, user=user)

    exact_document = exact_api.restv1(POST(
        'documents/Documents',
        dict(
            Type=invoice_type == 'tunga' and EXACT_DOCUMENT_TYPE_PURCHASE_INVOICE or EXACT_DOCUMENT_TYPE_SALES_INVOICE,
            Subject='{} - {}'.format(
                invoice.title,
                invoice_number
            ),
            Account=exact_user_id,
        )
    ))

    exact_api.restv1(POST(
        'documents/DocumentAttachments',
        dict(
            Attachment=base64.b64encode(invoice_file),
            Document=exact_document['ID'],
            FileName='{} - {}.pdf'.format(invoice.title, invoice_number)
        )
    ))

    if invoice_type == 'client':
        vat_code = EXACT_VAT_CODE_WORLD
        if vat_location == VAT_LOCATION_NL:
            vat_code = EXACT_VAT_CODE_NL
        elif vat_location == VAT_LOCATION_EUROPE:
            vat_code = EXACT_VAT_CODE_EUROPE
        exact_api.restv1(POST(
            'salesentry/SalesEntries',
            dict(
                Currency=CURRENCY_EUR,
                Customer=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_CLIENT_SALES,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                SalesEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_CLIENT_FEE,
                        VATCode=vat_code
                    )
                ]
            )
        ))
    elif invoice_type == 'tunga':
        exact_api.restv1(POST(
            'purchaseentry/PurchaseEntries',
            dict(
                Currency=CURRENCY_EUR,
                Supplier=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_DEVELOPER_PURCHASE,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                PurchaseEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_DEVELOPER_FEE
                    )
                ]
            )
        ))
    elif invoice_type == 'developer':
        exact_api.restv1(POST(
            'salesentry/SalesEntries',
            dict(
                Currency=CURRENCY_EUR,
                Customer=exact_user_id,
                Description=task.summary,
                Document=exact_document['ID'],
                EntryDate=invoice.created_at.isoformat(),
                Journal=EXACT_JOURNAL_DEVELOPER_SALES,
                ReportingPeriod=invoice.created_at.month,
                ReportingYear=invoice.created_at.year,
                YourRef=invoice_number,
                PaymentCondition=EXACT_PAYMENT_CONDITION_CODE_14_DAYS,
                SalesEntryLines=[
                    dict(
                        AmountFC=amount,
                        Description=invoice_number,
                        GLAccount=EXACT_GL_ACCOUNT_TUNGA_FEE
                    )
                ]
            )
        ))
