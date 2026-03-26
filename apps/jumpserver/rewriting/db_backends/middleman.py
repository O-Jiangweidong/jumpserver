import os
import sys

import urllib.parse

import requests

from django.conf import settings
from django.core.cache import cache

from common.utils import lazyproperty, get_logger, Singleton
from common.exceptions import JMSException


logger = get_logger(__name__)


class MiddlemanClient(metaclass=Singleton):
    def __init__(self):
        self._register_ok = False
        self._register()

    @property
    def enable(self):
        return self._register_ok

    @lazyproperty
    def _auth_token(self):
        value = cache.get('MIDDLEMAN_AUTH_TOKEN')
        if not value:
            access_key_path = os.path.join(settings.DATA_DIR, '.access_key')
            if os.path.exists(access_key_path):
                with open(access_key_path, 'r') as f:
                    value = f.read().strip()
        cache.set('MIDDLEMAN_AUTH_TOKEN', value, None)
        return f'Bearer {value}'

    def _request(self, method, url, query_params=None, **kwargs):
        if not self.enable:
            return

        url = settings.MIDDLEMAN_ENDPOINT + url
        if query_params:
            url = f'{url}&{urllib.parse.urlencode(query_params)}'
        kwargs.setdefault('headers', {})
        kwargs['headers']['Authorization'] = self._auth_token
        logger.debug(f'({method}) Request url: {url}')
        try:
            resp = requests.request(method, url, **kwargs)
            result = resp.json()
        except Exception as e:
            logger.error(f'({method}) Request url: {url} failed, error: {e}')
            raise JMSException("Request failed, middleman may not work")

        if resp.status_code >= 300:
            logger.error(f'({method}) Request url: {url} failed, error: {resp.text}')
            raise JMSException(resp.text)
        return result

    def __register(self):
        # TODO 从节点注册的时候需要把数据对齐，比如角色表可能在安装的时候就初始化了，middleman 中是不存在的
        logger.debug('Middleman client start register')

        from users.models import User

        token = settings.BOOTSTRAP_TOKEN
        md_endpoint = settings.MIDDLEMAN_ENDPOINT
        self_endpoint = settings.MIDDLEMAN_SELF_ENDPOINT
        name = settings.MIDDLEMAN_SERVICE_NAME
        role = settings.MIDDLEMAN_SERVICE_ROLE.lower()
        display = settings.MIDDLEMAN_SERVICE_DISPLAY
        ignore_same_name = settings.MIDDLEMAN_IGNORE_SAME_NAME
        if (not md_endpoint or
                not name or
                not self_endpoint or
                role not in ['replica', 'master']):
            logger.warning('The config of the middleman replica node is incomplete, skipping')
            return

        access_key_path = os.path.join(settings.DATA_DIR, '.access_key')
        if os.path.exists(access_key_path):
            with open(access_key_path, 'r') as f:
                cache.set('MIDDLEMAN_AUTH_TOKEN', f.read().strip(), None)
                self._register_ok = True
                return

        resp = None
        user, __ = User.objects.get_or_create(
            username=name, defaults={
                'name': display, 'username': name,
                'email': f'{name}@middleman.com',
                'is_first_login': False, 'created_by': 'System',
                'is_service_account': True,
            }
        )
        user.is_superuser = True
        logger.debug(f'Register middleman user[{user}] success')
        try:
            data = {
                'bootstrap_token': token, 'name': name,
                'private_token': str(user.private_token),
                'role': role, 'display': display, 'ignore_same_name': ignore_same_name,
                'endpoint': self_endpoint
            }
            resp = requests.post(f'{md_endpoint}/register/', json=data)
            resp.raise_for_status()
            resp_data = resp.json().get('data', {})
            with open(access_key_path, 'w') as f:
                auth_token = f"{resp_data.get('access_key')}:{resp_data.get('secret_key')}"
                cache.set('MIDDLEMAN_AUTH_TOKEN', auth_token, None)
                f.write(auth_token)
        except Exception as e:
            msg = resp.text if resp is not None and getattr(resp, 'text') else e
            logger.error('Failed to register middleman: %s' % msg)
            sys.exit(1)
        self._register_ok = True
        logger.debug('Middleman register successfully, role: %s' % role)

    def _register(self):
        lock_key = 'middleman:register:lock'

        if not cache.add(lock_key, 'locking', 10):
            logger.info('Another process is registering middleman, skip')
            return

        try:
            self.__register()
        finally:
            cache.delete(lock_key)

    def get_replicas(self, **kwargs):
        url = f'/middleman/replica-nodes/?{urllib.parse.urlencode(kwargs)}'
        return self._request('GET', url)

    def get_tasks(self, **kwargs):
        url = f'/middleman/tasks/?{urllib.parse.urlencode(kwargs)}'
        return self._request('GET', url)

    def sql_sync(self, replica_name, sql_type, sql, params, **kwargs):
        data = {'sql': sql, 'params': params, 'sql_type': sql_type}
        return self._request(
            'POST', f'/middleman/sql-sync/',
            json=data, headers={'REPLICA-NAME': replica_name}
        )
