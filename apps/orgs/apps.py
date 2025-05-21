import sys
import os

import requests

from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from common.utils import get_logger


logger = get_logger(__name__)


class OrgsConfig(AppConfig):
    name = 'orgs'
    verbose_name = _('App organizations')

    @staticmethod
    def _is_main_process():
        return os.environ.get('RUN_MAIN') == 'true'

    def _register_middleman(self):
        if not self._is_main_process():
            return

        access_key_path = os.path.join(settings.DATA_DIR, '.access_key')
        if os.path.exists(access_key_path):
            with open(access_key_path, 'r') as f:
                access_key = f.read().strip()
                if access_key:
                    settings.MIDDLEMAN_AUTH_TOKEN = access_key
                    return

        token = settings.BOOTSTRAP_TOKEN
        endpoint = settings.MIDDLEMAN_ENDPOINT
        name = settings.MIDDLEMAN_SERVICE_NAME
        role = settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower()
        display = settings.MIDDLEMAN_SERVICE_DISPLAY
        ignore_same_name = settings.MIDDLEMAN_IGNORE_SAME_NAME
        if not endpoint or not name or role not in ['slave', 'master']:
            logger.warning('The config of the Middleman slave node is incomplete, skipping')
            return

        resp = None
        try:
            data = {
                'bootstrap_token': token, 'name': name,
                'role': role, 'display': display, 'ignore_same_name': ignore_same_name
            }
            resp = requests.post(f'{endpoint}/register/', json=data)
            resp.raise_for_status()
            resp_data = resp.json().get('data', {})
            with open(access_key_path, 'w') as f:
                f.write(f"{resp_data.get('access_key')}:{resp_data.get('secret_key')}")
        except Exception as e:
            msg = resp.text if resp is not None and getattr(resp, 'text') else e
            logger.error('Failed to register middleman: %s' % msg)
            sys.exit(1)
        logger.debug('Middleman register successfully, role: %s' % role)

    def ready(self):
        self._register_middleman()

        from . import signal_handlers  # noqa
        from . import tasks  # noqa
        super().ready()
