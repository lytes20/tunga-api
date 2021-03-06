from django.contrib.auth import get_user_model

from tunga.settings import DEBUG
from tunga_profiles.models import AppIntegration
from tunga_utils.constants import STATUS_APPROVED, STATUS_PENDING, STATUS_INITIATED
from tunga_utils.helpers import clean_instance


def profile_check(user):
    user = clean_instance(user, get_user_model())
    data_source = user.is_project_owner and user.company or user.profile
    if not user.first_name or not user.last_name or not user.email or not data_source:
        return False

    if user.is_developer and user.payoneer_status not in [STATUS_APPROVED, STATUS_PENDING, STATUS_INITIATED] and not DEBUG:
        return False

    required = ['country', 'city', 'street', 'plot_number', 'postal_code']

    if user.is_developer or user.is_project_manager:
        required.extend(['id_document'])
    elif user.is_project_owner:
        required.extend(['name'])
        if user.tax_location == 'europe':
            required.extend(['vat_number'])

    profile_dict = data_source.__dict__
    for key in profile_dict:
        if key in required and not profile_dict[key]:
            return False
    return True


def get_app_integration(user, provider):
    try:
        return AppIntegration.objects.filter(user=user, provider=provider).latest('updated_at')
    except AppIntegration.DoesNotExist:
        return None
