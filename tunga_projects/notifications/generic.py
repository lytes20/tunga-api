from django_rq import job

from tunga_projects.notifications.email import notify_new_participant_email_dev, \
    notify_new_progress_report_email_client, remind_progress_event_email, notify_new_project_email_dev
from tunga_projects.notifications.slack import notify_new_progress_report_slack, \
    notify_missed_progress_event_slack, notify_new_project_slack


@job
def notify_new_project(project):
    notify_new_project_slack(project)
    notify_new_project_email_dev(project)


@job
def notify_new_participant(participation):
    notify_new_participant_email_dev(participation)


@job
def remind_progress_event(progress_event):
    remind_progress_event_email(progress_event)


@job
def notify_new_progress_report(progress_report):
    notify_new_progress_report_email_client(progress_report)
    notify_new_progress_report_slack(progress_report, updated=False)


@job
def notify_missed_progress_event(instance):
    notify_missed_progress_event_slack(instance)
