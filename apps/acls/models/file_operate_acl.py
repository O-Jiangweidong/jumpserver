from django.db import models
from django.utils.translation import gettext_lazy as _

from ops.const import Types
from .base import UserAssetAccountBaseACL, CustomACLModelMixin


class AssetFileOperateACL(CustomACLModelMixin, UserAssetAccountBaseACL):
    reviewers_2 = models.ManyToManyField(
        'users.User', blank=True, verbose_name=_("Reviewers 2"),
        related_name='asset_file_operate_acl_reviewers_2'
    )

    class Meta(UserAssetAccountBaseACL.Meta):
        verbose_name = _('Asset file operate acl')
        abstract = False

    def __str__(self):
        return self.name

    def create_asset_file_review_ticket(self, user, asset, account, extra_info):
        from tickets.const import TicketType
        from tickets.models import ApplyAssetFileTicket

        action = Types(extra_info["action"]).label
        title = f'[{action}] ' + _('Asset file confirm') + f': {user}'
        data = {
            'title': title,
            'org_id': self.org_id,
            'applicant': user,
            'apply_login_user': user,
            'apply_login_asset': asset,
            'apply_login_account': account,
            'type': TicketType.file_confirm,
            'meta': extra_info,
        }
        ticket = ApplyAssetFileTicket.objects.create(**data)
        ticket.set_webhook_url(self.webhook_url)
        ticket.open_by_system(self.reviewers.all(), self.reviewers_2.all())
        return ticket
