import shutil

from django.conf import settings
from django.utils._os import safe_join

from common.utils import get_logger
from ops.tasks import run_file_job_execution_with_ticket
from tickets.models import ApplyAssetFileTicket
from .base import BaseHandler

logger = get_logger(__file__)


class Handler(BaseHandler):
    ticket: ApplyAssetFileTicket

    def __do_file_action(self):
        run_file_job_execution_with_ticket.delay(self.ticket.id)

    def __clear_files(self):
        upload_file_dir = safe_join(settings.SHARE_DIR, 'job_upload_file')
        job_id = self.ticket.meta.get('job_id')
        if not job_id:
            return

        path = safe_join(upload_file_dir, str(job_id))
        try:
            shutil.rmtree(path)
        except OSError as e:
            print(f"del upload tmp dir {path} failed! {e}")

    def __handle_reject_or_closed(self):
        if self.ticket.meta.get('action') == 'upload_file':
            self.__clear_files()
        self.ticket.set_file_status(status='cancel')

    def _on_step_approved(self, step):
        is_finished = super()._on_step_approved(step)
        if is_finished:
            self.__do_file_action()

    def _on_step_rejected(self, step):
        super()._on_step_rejected(step)
        self.__handle_reject_or_closed()

    def _on_step_closed(self, step):
        super()._on_step_closed(step)
        self.__handle_reject_or_closed()
