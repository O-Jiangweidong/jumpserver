from django.db import models
from django.utils.translation import gettext_lazy as _

from .general import Ticket, CustomCacheMixin

__all__ = ['ApplyAssetFileTicket']

from ...const import TicketType


class ApplyAssetFileTicket(CustomCacheMixin, Ticket):
    apply_login_user = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, verbose_name=_('Login user'),
    )
    apply_login_asset = models.ForeignKey(
        'assets.Asset', on_delete=models.SET_NULL, null=True, verbose_name=_('Login asset'),
    )
    apply_login_account = models.CharField(
        max_length=128, default='', verbose_name=_('Login account')
    )

    TICKET_TYPE = TicketType.file_confirm

    class Meta:
        verbose_name = _('Apply Asset File Operate Ticket')

    def set_file_status(self, status='failed', info_mapping=None):
        meta = self.meta or {}
        info_mapping = info_mapping or {}
        src_path_info = meta.get('src_path_info', [])
        new_result = []
        for path_info in src_path_info:
            other = info_mapping.get(path_info['filename'])
            if isinstance(other, dict):
                path_info.update(other)
            else:
                path_info['status'] = status
            new_result.append(path_info)
        meta['src_path_info'] = new_result
        self.meta = meta
        self.save(update_fields=['meta'])
