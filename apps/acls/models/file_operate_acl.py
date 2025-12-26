from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import UserAssetAccountBaseACL


class AssetFileOperateACL(UserAssetAccountBaseACL):
    reviewers_2 = models.ManyToManyField(
        'users.User', blank=True, verbose_name=_("Reviewers 2"),
        related_name='asset_file_operate_acl_reviewers_2'
    )

    class Meta(UserAssetAccountBaseACL.Meta):
        verbose_name = _('Asset file operate acl')
        abstract = False

    def __str__(self):
        return self.name

    def create_asset_file_review_ticket(self, user, asset, account, file_info):
        from tickets.const import TicketType
        from tickets.models import ApplyAssetFileTicket
        title = _('Asset file confirm') + ' ({})'.format(user)
        data = {
            'title': title,
            'org_id': self.org_id,
            'applicant': user,
            'apply_login_user': user,
            'apply_login_asset': asset,
            'apply_login_account': account,
            'type': TicketType.file_confirm,
            'meta': file_info,
        }
        ticket = ApplyAssetFileTicket.objects.create(**data)
        ticket.open_by_system(self.reviewers.all(), self.reviewers_2.all())
        return ticket
