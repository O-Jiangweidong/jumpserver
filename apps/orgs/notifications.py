from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from common.utils import get_logger
from notifications.notifications import UserMessage


logger = get_logger(__name__)

__all__ = (
    'OrganizationAssetLimitWarning',
)


class OrganizationAssetLimitWarning(UserMessage):
    def __init__(self, user, organizations):
        super().__init__(user)
        self.organizations = organizations

    def get_html_msg(self) -> dict:
        subject = str(_('Organization asset limit warning'))
        context = {
            'org_infos': [
                {
                    'name': org.name,
                    'asset_limit': org.asset_limit,
                    'current_asset_count': org.resource_statistics_cache.assets_amount,
                }
                for org in self.organizations],
        }
        message = render_to_string('orgs/_msg_check_org_asset_limit.html', context)
        return {
            'subject': subject, 'message': message
        }
