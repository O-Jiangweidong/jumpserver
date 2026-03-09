import requests

from celery import shared_task
from django.conf import settings

from tickets.models import ApplyCommandTicket
from common.utils import get_logger
from .base import BaseHandler


logger = get_logger(__name__)


@shared_task(verbose_name='Send command review ticket message')
def send_message_to_external(url, data):
    try:
        resp = requests.post(url, json=data)
        resp.raise_for_status()
    except Exception as error:
        logger.error(f'Error sending command review ticket message: {error}')


class Handler(BaseHandler):
    ticket: ApplyCommandTicket

    def _on_pending(self):
        super()._on_pending()

        url = settings.COMMAND_REVIEW_TICKET_MESSAGE_URL
        if not url:
            return

        ticket = self.ticket
        data = {
            'ticket_id': str(ticket.id),
            'session_id': str(ticket.apply_from_session.id),
            'serial_num': ticket.serial_num,
            'applicant': str(ticket.applicant),
            'apply_run_account': ticket.apply_run_account,
            'apply_run_user': str(ticket.apply_run_user),
            'apply_run_asset': ticket.apply_run_asset,
            'apply_run_command': ticket.apply_run_command,
            'apply_from_cmd_filter_acl_id': str(ticket.apply_from_cmd_filter_acl.id),
            'apply_from_cmd_filter_acl': str(ticket.apply_from_cmd_filter_acl),
        }
        send_message_to_external.delay(url, data)
