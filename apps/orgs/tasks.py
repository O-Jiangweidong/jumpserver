from celery import shared_task
from django.utils.translation import gettext_lazy as _

from common.utils import get_logger
from ops.celery.decorator import register_as_period_task
from users.models import User
from .models import Organization
from .notifications import OrganizationAssetLimitWarning


logger = get_logger(__file__)


@shared_task(verbose_name=_("Refresh organization cache"))
def refresh_org_cache_task(*fields):
    from .caches import OrgResourceStatisticsCache
    OrgResourceStatisticsCache.refresh(*fields)
    check_server_performance_period()


@shared_task(verbose_name=_("Periodic check organization asset limit"))
@register_as_period_task(interval=3600)
def check_server_performance_period():
    orgs = []
    for org in Organization.objects.all():
        if org.is_over_asset_limit:
            orgs.append(org)

    if not orgs:
        return

    users = User.get_super_admins()
    for user in users:
        OrganizationAssetLimitWarning(user, orgs).publish()
