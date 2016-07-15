import datetime
import json
from urllib import urlencode

from dateutil.parser import parse
from django.http.response import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from dry_rest_permissions.generics import DRYPermissions, DRYObjectPermissions
from oauthlib import oauth1
from oauthlib.oauth1 import SIGNATURE_TYPE_QUERY
from rest_framework import viewsets, status
from rest_framework.decorators import detail_route, api_view, permission_classes
from rest_framework.exceptions import ValidationError, NotAuthenticated, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from weasyprint import HTML

from tunga.settings import BITONIC_CONSUMER_KEY, BITONIC_CONSUMER_SECRET, BITONIC_ACCESS_TOKEN, BITONIC_TOKEN_SECRET, \
    BITONIC_URL
from tunga_activity.filters import ActionFilter
from tunga_activity.serializers import SimpleActivitySerializer
from tunga_tasks import slugs
from tunga_tasks.emails import send_task_invoice_request_email
from tunga_tasks.filterbackends import TaskFilterBackend, ApplicationFilterBackend, ParticipationFilterBackend, \
    TaskRequestFilterBackend, SavedTaskFilterBackend, ProjectFilterBackend, ProgressReportFilterBackend, \
    ProgressEventFilterBackend
from tunga_tasks.filters import TaskFilter, ApplicationFilter, ParticipationFilter, TaskRequestFilter, SavedTaskFilter, \
    ProjectFilter, ProgressReportFilter, ProgressEventFilter
from tunga_tasks.models import Task, Application, Participation, TaskRequest, SavedTask, Project, ProgressReport, ProgressEvent, \
    Integration, IntegrationMeta, IntegrationActivity, TASK_PAYMENT_METHOD_BITONIC, TaskPayment, \
    TASK_PAYMENT_METHOD_BANK
from tunga_tasks.renderers import PDFRenderer
from tunga_tasks.serializers import TaskSerializer, ApplicationSerializer, ParticipationSerializer, \
    TaskRequestSerializer, SavedTaskSerializer, ProjectSerializer, ProgressReportSerializer, ProgressEventSerializer, \
    IntegrationSerializer, TaskPaymentSerializer, TaskInvoiceSerializer
from tunga_tasks.tasks import distribute_task_payment
from tunga_utils import github, coinbase_utils, bitcoin_utils
from tunga_utils.filterbackends import DEFAULT_FILTER_BACKENDS
from tunga_utils.mixins import SaveUploadsMixin
from tunga_utils.views import get_social_token


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Project Resource
    ---
    list:
        parameters_strategy: merge
        parameters:
            - name: filter
              description: Project filter e.g [running]
              type: string
              paramType: query
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProjectFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProjectFilterBackend,)
    search_fields = ('title', 'description')


class TaskViewSet(viewsets.ModelViewSet, SaveUploadsMixin):
    """
    Task Resource
    ---
    list:
        parameters_strategy: merge
        parameters:
            - name: filter
              description: Task filter e.g [running, my-tasks, saved, skills, my-clients]
              type: string
              paramType: query
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = TaskFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (TaskFilterBackend,)
    search_fields = ('title', 'description', 'skills__name')

    @detail_route(
        methods=['get'], url_path='activity',
        permission_classes=[IsAuthenticated],
        serializer_class=SimpleActivitySerializer,
        filter_class=None,
        filter_backends=DEFAULT_FILTER_BACKENDS,
        search_fields=('comments__body',)
    )
    def activity(self, request, pk=None):
        """
        Task Activity Endpoint
        ---
        response_serializer: SimpleActivitySerializer
        omit_parameters:
            - query
        """
        task = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, task)

        queryset = ActionFilter(request.GET, self.filter_queryset(task.target_actions.all()))
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @detail_route(
        methods=['get'], url_path='meta',
        permission_classes=[IsAuthenticated]
    )
    def meta(self, request, pk=None):
        """
        Get task meta data
        ---
        omit_serializer: true
        omit_parameters:
            - query
        """
        task = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, task)

        payment_meta = task.meta_payment
        payment_meta['task_url'] = '%s://%s%s' % (request.scheme, request.get_host(), payment_meta['task_url'])
        payment = json.dumps(payment_meta)
        return Response({'task': task.id, 'participation': {}, 'payment': payment})

    @detail_route(
        methods=['get', 'post', 'put'], url_path='invoice',
        serializer_class=TaskPaymentSerializer
    )
    def invoice(self, request, pk=None):
        """
        Task Invoice Endpoint
        ---
        request_serializer: TaskPaymentSerializer
        response_serializer: TaskSerializer
        omit_parameters:
            - query
        """
        task = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, task)

        has_updated = False

        if request.method == 'POST':
            serializer = self.get_serializer(task, data=request.data)
            serializer.is_valid(raise_exception=True)

            fee = serializer.validated_data['fee']
            payment_method = serializer.validated_data['payment_method']

            if fee < task.fee:
                raise ValidationError({
                    'fee': 'You cannot reduce the fee for the task, Please contact support@tunga.io for assistance'
                })

            task.fee = fee
            task.payment_method = payment_method

            btc_price = coinbase_utils.get_btc_price(task.currency)
            task.btc_price = btc_price
            has_updated = True

        if not task.btc_address or not bitcoin_utils.is_valid_btc_address(task.btc_address):
            has_updated = True
            address = coinbase_utils.get_new_address(coinbase_utils.get_api_client())
            task.btc_address = address

        if has_updated:
            task.invoice_date = datetime.datetime.utcnow()
            task.full_clean()
            task.save()

            if task.payment_method == TASK_PAYMENT_METHOD_BANK:
                # Send notification for requested invoice
                send_task_invoice_request_email.delay(task.id)

        response_serializer = self.get_serializer(task)
        return Response(response_serializer.data)

    @detail_route(
        methods=['get'], url_path='pay/(?P<provider>[^/]+)'
    )
    def pay(self, request, pk=None, provider=None):
        """
            Task Payment Provider Endpoint
            ---
            omit_serializer: true
            omit_parameters:
                - query
            """
        task = self.get_object()
        callback = '%s://%s/task/%s/pay/' % (request.scheme, request.get_host(), pk)
        next_url = callback
        if task and task.has_object_write_permission(request) and bitcoin_utils.is_valid_btc_address(task.btc_address):
            if provider == TASK_PAYMENT_METHOD_BITONIC:
                client = oauth1.Client(
                    BITONIC_CONSUMER_KEY, BITONIC_CONSUMER_SECRET, BITONIC_ACCESS_TOKEN, BITONIC_TOKEN_SECRET,
                    callback_uri=callback, signature_type=SIGNATURE_TYPE_QUERY
                )
                amount = task.fee
                q_string = urlencode({
                    'ext_data': task.summary.encode('utf-8'),
                    'bitcoinaddress': task.btc_address,
                    'ordertype': 'buy',
                    'euros': amount
                })
                req_data = client.sign('%s/?%s' % (BITONIC_URL, q_string), http_method='GET')
                next_url = req_data[0]
        return redirect(next_url)

    @detail_route(
        methods=['get'], url_path='download/invoice',
        renderer_classes=[PDFRenderer, StaticHTMLRenderer]
    )
    def download_invoice(self, request, pk=None):
        """
        Download Task Invoice Endpoint
        ---
        omit_serializer: True
        omit_parameters:
            - query
        """
        task = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            self.check_object_permissions(request, task)
        except NotAuthenticated:
            return redirect('/?next=%s' % reverse(request.resolver_match.url_name, kwargs={'pk': pk}))
        except PermissionDenied:
            return HttpResponse("You do not have permission to access this item")

        participation = None
        try:
            participation = task.participation_set.filter(accepted=True).order_by('-assignee').earliest('created_at')
        except:
            pass

        if participation:
            invoice = TaskInvoiceSerializer(task).data
            ctx = {
                'user': request.user, 'invoice': invoice
            }

            rendered_html = render_to_string("tunga/pdf/invoice.html", context=ctx).encode(encoding="UTF-8")
            if request.accepted_renderer.format == 'html':
                return HttpResponse(rendered_html)
            pdf_file = HTML(string=rendered_html, encoding='utf-8').write_pdf()
            http_response = HttpResponse(pdf_file, content_type='application/pdf')
            http_response['Content-Disposition'] = 'filename="invoice_%s.pdf"' % task.summary
            return http_response

        return HttpResponse("Could not generate an invoice, Please contact support@tunga.io")

    @detail_route(
        methods=['get', 'post', 'put', 'patch'], url_path='integration/(?P<provider>[^/]+)',
        serializer_class=IntegrationSerializer
    )
    def integration(self, request, pk=None, provider=None):
        """
        Manage Task Integrations
        ---
        serializer: IntegrationSerializer
        omit_parameters:
            - query
        """
        get_object_or_404(self.queryset, pk=pk)
        queryset = Integration.objects.filter(task_id=pk, provider=provider)
        if request.method == 'GET':
            instance = get_object_or_404(queryset)
            self.check_object_permissions(request, instance)
            serializer = self.get_serializer(instance, context={'request': request})
            return Response(serializer.data)
        elif request.method == 'POST':
            request_data = dict(request.data)
            request_data['provider'] = provider
            request_data['task'] = pk

            try:
                instance = queryset.latest('created_at')
            except Integration.DoesNotExist:
                instance = None

            secret = get_random_string()
            if instance:
                self.check_object_permissions(request, instance)
                secret = instance.secret or secret
            else:
                self.check_permissions(request)
            serializer = self.get_serializer(instance, data=request_data, context={'request': request})
            serializer.is_valid(raise_exception=True)

            data = {
                'name': 'web',
                'config': {
                    'url': '%s://%s/task/%s/hook/%s/' % (request.scheme, request.get_host(), pk, provider),
                    'content_type': 'json',
                    'secret': secret
                },
                'events': github.transform_to_github_events(request_data['events']),
                'active': True
            }

            repo_full_name = None
            repo = request_data.get('repo', None)
            if repo:
                repo_full_name = repo.get('full_name', None)
            if not repo_full_name and instance:
                repo_full_name = instance.repo_full_name

            if not repo_full_name:
                return Response({'status': 'Bad Request'}, status.HTTP_400_BAD_REQUEST)

            web_hook_endpoint = '/repos/%s/hooks' % repo_full_name
            hook_method = 'post'

            if instance and instance.hook_id:
                web_hook_endpoint += '/%s' % instance.hook_id
                hook_method = 'patch'

            social_token = get_social_token(user=request.user, provider=provider)
            if not social_token:
                return Response({'status': 'Unauthorized'}, status.HTTP_401_UNAUTHORIZED)

            r = github.api(endpoint=web_hook_endpoint, method=hook_method, data=data, access_token=social_token.token)
            if r.status_code in [200, 201]:
                hook = r.json()
                integration = serializer.save(secret=secret)
                if 'id' in hook:
                    IntegrationMeta.objects.update_or_create(
                            integration=integration, meta_key='hook_id', defaults={'meta_value': hook['id']}
                    )
                return Response(serializer.data)
            return Response(r.json(), r.status_code)
        else:
            return Response({'status': 'Method not allowed'}, status.HTTP_405_METHOD_NOT_ALLOWED)

    @detail_route(
        methods=['post'], url_path='hook/(?P<provider>[^/]+)',
        permission_classes=[AllowAny]
    )
    def hook(self, request, pk=None, provider=None):
        """
        Task Integration Hook
        Receives web hooks from different providers
        ---
        omit_serializer: true
        omit_parameters:
            - query
        """
        try:
            integration = Integration.objects.filter(task_id=pk, provider=provider).latest('created_at')
        except:
            integration = None
        if integration:
            github_event_name = request.META.get(github.HEADER_EVENT_NAME, None)
            delivery_id = request.META.get(github.HEADER_DELIVERY_ID, None)
            activity = {}
            if github_event_name:
                payload = request.data

                if github_event_name == github.EVENT_PUSH:
                    # Push event
                    if payload[github.PAYLOAD_HEAD_COMMIT]:
                        head_commit = payload[github.PAYLOAD_HEAD_COMMIT]
                        activity[slugs.ACTIVITY_URL] = head_commit[github.PAYLOAD_URL]
                        activity[slugs.ACTIVITY_REF] = head_commit[github.PAYLOAD_ID]
                        activity[slugs.ACTIVITY_REF_NAME] = head_commit[github.PAYLOAD_TREE_ID]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_BODY] = head_commit[github.PAYLOAD_MESSAGE]
                        activity[slugs.ACTIVITY_CREATED_AT] = parse(head_commit[github.PAYLOAD_TIMESTAMP])
                elif github_event_name == github.EVENT_ISSUE:
                    # Issue
                    issue_actions = [
                        github.PAYLOAD_ACTION_OPENED, github.PAYLOAD_ACTION_CLOSED,
                        github.PAYLOAD_ACTION_EDITED, github.PAYLOAD_ACTION_REOPENED
                    ]
                    if payload[github.PAYLOAD_ISSUE] and payload[github.PAYLOAD_ACTION] in issue_actions:
                        issue = payload[github.PAYLOAD_ISSUE]
                        activity[slugs.ACTIVITY_ACTION] = payload[github.PAYLOAD_ACTION]
                        activity[slugs.ACTIVITY_URL] = issue[github.PAYLOAD_HTML_URL]
                        activity[slugs.ACTIVITY_REF] = issue[github.PAYLOAD_ID]
                        activity[slugs.ACTIVITY_REF_NAME] = issue[github.PAYLOAD_NUMBER]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_TITLE] = issue[github.PAYLOAD_TITLE]
                        activity[slugs.ACTIVITY_BODY] = issue[github.PAYLOAD_BODY]
                        activity[slugs.ACTIVITY_CREATED_AT] = parse(issue[github.PAYLOAD_CREATED_AT])
                elif github_event_name == github.EVENT_PULL_REQUEST:
                    # Pull Request
                    pull_request_actions = [
                        github.PAYLOAD_ACTION_OPENED, github.PAYLOAD_ACTION_CLOSED,
                        github.PAYLOAD_ACTION_EDITED, github.PAYLOAD_ACTION_REOPENED
                    ]
                    if payload[github.PAYLOAD_PULL_REQUEST] and payload[github.PAYLOAD_ACTION] in pull_request_actions:
                        pull_request = payload[github.PAYLOAD_PULL_REQUEST]
                        is_merged = payload[github.PAYLOAD_ACTION] == github.PAYLOAD_ACTION_CLOSED and pull_request[github.PAYLOAD_MERGED]
                        activity[slugs.ACTIVITY_ACTION] = is_merged and slugs.ACTION_MERGED or payload[github.PAYLOAD_ACTION]
                        activity[slugs.ACTIVITY_URL] = pull_request[github.PAYLOAD_HTML_URL]
                        activity[slugs.ACTIVITY_REF] = pull_request[github.PAYLOAD_ID]
                        activity[slugs.ACTIVITY_REF_NAME] = pull_request[github.PAYLOAD_NUMBER]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_TITLE] = pull_request[github.PAYLOAD_TITLE]
                        activity[slugs.ACTIVITY_BODY] = pull_request[github.PAYLOAD_BODY]
                        activity[slugs.ACTIVITY_CREATED_AT] = parse(pull_request[github.PAYLOAD_CREATED_AT])
                elif github_event_name in [github.EVENT_CREATE, github.EVENT_DELETE]:
                    # Branch and Tag creation and deletion
                    tracked_ref_types = [github.PAYLOAD_REF_TYPE_BRANCH, github.PAYLOAD_REF_TYPE_TAG]
                    if payload[github.PAYLOAD_REF_TYPE] in tracked_ref_types:
                        activity[slugs.ACTIVITY_EVENT_ID] = payload[github.PAYLOAD_REF_TYPE] == github.PAYLOAD_REF_TYPE_BRANCH and slugs.BRANCH or slugs.TAG
                        activity[slugs.ACTIVITY_ACTION] = github_event_name == github.EVENT_CREATE and slugs.ACTION_CREATED or slugs.ACTION_DELETED
                        activity[slugs.ACTIVITY_URL] = '%s/tree/%s' % (
                            payload[github.PAYLOAD_REPOSITORY][github.PAYLOAD_HTML_URL], payload[github.PAYLOAD_REF]
                        )
                        activity[slugs.ACTIVITY_REF] = payload[github.PAYLOAD_REF]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                elif github_event_name in [github.EVENT_COMMIT_COMMENT, github.EVENT_ISSUE_COMMENT, github.EVENT_PULL_REQUEST_REVIEW_COMMENT]:
                    # Commit, Issue and Pull Request comments
                    if payload[github.PAYLOAD_ACTION] == github.PAYLOAD_ACTION_CREATED:
                        comment = payload[github.PAYLOAD_COMMENT]
                        activity[slugs.ACTIVITY_ACTION] = slugs.ACTION_CREATED
                        activity[slugs.ACTIVITY_URL] = comment[github.PAYLOAD_HTML_URL]
                        activity[slugs.ACTIVITY_REF] = comment[github.PAYLOAD_ID]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_BODY] = comment[github.PAYLOAD_BODY]
                        activity[slugs.ACTIVITY_CREATED_AT] = parse(comment[github.PAYLOAD_CREATED_AT])
                elif github_event_name == github.EVENT_RELEASE:
                    # Release
                    release_actions = [github.PAYLOAD_ACTION_PUBLISHED]
                    if payload[github.PAYLOAD_RELEASE] and payload[github.PAYLOAD_ACTION] in release_actions:
                        release = payload[github.PAYLOAD_RELEASE]
                        activity[slugs.ACTIVITY_ACTION] = payload[github.PAYLOAD_ACTION]
                        activity[slugs.ACTIVITY_URL] = release[github.PAYLOAD_HTML_URL]
                        activity[slugs.ACTIVITY_REF] = release[github.PAYLOAD_ID]
                        activity[slugs.ACTIVITY_REF_NAME] = release[github.PAYLOAD_TAG_NAME]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_TITLE] = release[github.PAYLOAD_TITLE]
                        activity[slugs.ACTIVITY_BODY] = release[github.PAYLOAD_BODY]
                        activity[slugs.ACTIVITY_CREATED_AT] = parse(release[github.PAYLOAD_CREATED_AT])
                elif github_event_name == github.EVENT_GOLLUM:
                    # Wiki creation and updates
                    if payload[github.PAYLOAD_PAGES]:
                        first_page = payload[github.PAYLOAD_PAGES][0]
                        activity[slugs.ACTIVITY_ACTION] = first_page[github.PAYLOAD_ACTION] == github.PAYLOAD_ACTION_CREATED and slugs.ACTION_CREATED or slugs.ACTION_EDITED
                        activity[slugs.ACTIVITY_URL] = first_page[github.PAYLOAD_HTML_URL]
                        activity[slugs.ACTIVITY_REF] = payload[github.PAYLOAD_PAGE_NAME]
                        activity[slugs.ACTIVITY_USERNAME] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_USERNAME]
                        activity[slugs.ACTIVITY_AVATAR_URL] = payload[github.PAYLOAD_SENDER][github.PAYLOAD_AVATAR_URL]
                        activity[slugs.ACTIVITY_BODY] = first_page[github.PAYLOAD_SUMMARY]

                if activity:
                    if not activity.get(slugs.ACTIVITY_EVENT_ID, None):
                        activity[slugs.ACTIVITY_EVENT_ID] = github.transform_to_tunga_event(github_event_name)
                    activity[slugs.ACTIVITY_INTEGRATION] = integration
                    IntegrationActivity.objects.create(**activity)
        return Response({'status': 'Received'})


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    Task Application Resource
    """
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ApplicationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ApplicationFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ParticipationViewSet(viewsets.ModelViewSet):
    """
    Task Participation Resource
    """
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer
    permission_classes = [IsAuthenticated, DRYObjectPermissions]
    filter_class = ParticipationFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ParticipationFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class TaskRequestViewSet(viewsets.ModelViewSet):
    """
    Task Request Resource
    """
    queryset = TaskRequest.objects.all()
    serializer_class = TaskRequestSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = TaskRequestFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (TaskRequestFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class SavedTaskViewSet(viewsets.ModelViewSet):
    """
    Saved Task Resource
    """
    queryset = SavedTask.objects.all()
    serializer_class = SavedTaskSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = SavedTaskFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (SavedTaskFilterBackend,)
    search_fields = ('task__title', 'task__skills__name', '^user__username', '^user__first_name', '^user__last_name')


class ProgressEventViewSet(viewsets.ModelViewSet):
    """
    Progress Event Resource
    """
    queryset = ProgressEvent.objects.all()
    serializer_class = ProgressEventSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProgressEventFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProgressEventFilterBackend,)
    search_fields = (
        'title', 'description', 'task__title', 'task__skills__name',
        '^created_by__user__username', '^created_by__user__first_name', '^created_by__user__last_name',
    )


class ProgressReportViewSet(viewsets.ModelViewSet):
    """
    Progress Report Resource
    """
    queryset = ProgressReport.objects.all()
    serializer_class = ProgressReportSerializer
    permission_classes = [IsAuthenticated, DRYPermissions]
    filter_class = ProgressReportFilter
    filter_backends = DEFAULT_FILTER_BACKENDS + (ProgressReportFilterBackend,)
    search_fields = (
        '^user__username', '^user__first_name', '^user__last_name', 'accomplished', 'next_steps', 'remarks',
        'event__task__title', 'event__task__skills__name'
    )


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes([AllowAny])
def coinbase_notification_url(request):
    client = coinbase_utils.get_api_client()

    # Verify that the request came from coinbase
    cb_signature = request.META.get(coinbase_utils.HEADER_COINBASE_SIGNATURE, None)
    if not client.verify_callback(request.body, cb_signature):
        return Response('Unauthorized Request', status=status.HTTP_401_UNAUTHORIZED)

    payload = request.data
    if payload.get(coinbase_utils.PAYLOAD_TYPE, None) == coinbase_utils.PAYLOAD_TYPE_NEW_PAYMENT:
        id = payload[coinbase_utils.PAYLOAD_ID]
        address = payload[coinbase_utils.PAYLOAD_DATA][coinbase_utils.PAYLOAD_ADDRESS]
        paid_at = parse(payload[coinbase_utils.PAYLOAD_DATA][coinbase_utils.PAYLOAD_CREATED_AT], ignoretz=True)
        amount = payload[coinbase_utils.PAYLOAD_ADDITIONAL_DATA][coinbase_utils.PAYLOAD_AMOUNT][coinbase_utils.PAYLOAD_AMOUNT]

        try:
            task = Task.objects.filter(btc_address=address).latest('created_at')
        except:
            task = None

        if task:
            TaskPayment.objects.get_or_create(
                task=task, ref=id, btc_address=task.btc_address, defaults={'btc_received': amount, 'btc_price': task.btc_price, 'received_at':paid_at}
            )
            Task.objects.filter(id=task.id).update(paid=True, paid_at=paid_at)

            distribute_task_payment.delay(task.id)
    return Response('Received')
