from celery import shared_task
from django.utils.translation import gettext_lazy as _

from common.utils import get_logger
from ops.celery.decorator import register_as_period_task
from users.models import User
from .notifications import OrganizationAssetLimitWarning
from .utils import get_current_org


logger = get_logger(__file__)


@shared_task(verbose_name=_("Refresh organization cache"))
def refresh_org_cache_task(*fields):
    from .caches import OrgResourceStatisticsCache
    OrgResourceStatisticsCache.refresh(*fields)


@shared_task(verbose_name=_("Periodic check organization asset limit"))
@register_as_period_task(interval=3600)
def check_server_performance_period():
    from assets.models import Asset
    orgs = []
    cur_org = get_current_org()
    if cur_org and cur_org.is_root():
        return

    asset_count = Asset.objects.filter(org_id=cur_org.id).count()
    if asset_count > cur_org.asset_limit:
        orgs.append({
            'name': cur_org.name,
            'asset_limit': cur_org.asset_limit,
            'current_asset_count': asset_count,
        })
    if not orgs:
        return

    users = User.get_super_admins()
    for user in users:
        OrganizationAssetLimitWarning(user, orgs).publish()
