import requests

from typing import Iterable, AnyStr

from common.utils import get_logger
from .base import BackendBase


logger = get_logger(__name__)


class WebhookClient(object):
    @staticmethod
    def send_text(users: Iterable, msg: AnyStr, **kwargs):
        users = tuple(users)
        logger.info(f'Wecom webhook send text: users={users} msg={msg}')
        webhook_url = kwargs.get('webhook_url')
        if not webhook_url:
            return

        at_user = ', '.join([f'<@{u}>' for u in users])
        data = {
            'msgtype': 'markdown',
            'markdown': {'content': msg + f'\r\n{at_user}'}
        }

        try:
            res = requests.post(webhook_url, json=data).json()
            errcode = res.get('errcode', -1)
            if str(errcode) != '0':
                raise ValueError(res.get('errmsg', _('Unknown')))
        except Exception as e:
            logger.error(f'Wecom send msg with webhook error: {e}')


class WeComWebhook(BackendBase):
    account_field = 'wecom_id'
    is_enable_field_in_settings = 'SECRET_KEY'

    def send_msg(self, users, message, subject=None, webhook_url=None):
        accounts, __, __ = self.get_accounts(users)
        if not accounts:
            return

        return WebhookClient().send_text(accounts, message, webhook_url=webhook_url)


backend = WeComWebhook
