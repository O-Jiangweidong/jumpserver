from celery import shared_task
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from assets.models import Asset
from common.const.crontab import CRONTAB_AT_AM_THREE
from ops.celery.decorator import register_as_period_task


@shared_task(verbose_name=_('Periodic reset of asset weights'))
# @register_as_period_task(crontab=CRONTAB_AT_AM_THREE)
def rebuild_asset_weight():
    print("Start resetting asset weights.")
    count, weight, bulk_size = 0, 0, 1000
    total_assets = []
    while True:
        assets = Asset.objects.order_by('weight').only('id', 'weight')[count:count + bulk_size]
        if not assets:
            break

        for asset in assets:
            asset.weight = weight
            weight += 1000
        total_assets.extend(assets)
        count += len(assets)

    with transaction.atomic():
        for step in range(0, len(total_assets), bulk_size):
            Asset.objects.bulk_update(total_assets[step:step+bulk_size], ['weight'])
