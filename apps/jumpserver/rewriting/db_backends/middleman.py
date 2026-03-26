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

    @staticmethod
    def _datetime(value):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f") if value else None

    @staticmethod
    def _uuid(value, replace=True):
        if not value:
            return None

        value = str(value)
        if replace:
            return value.replace('-', '')
        return value

    @staticmethod
    def _num(value):
        return 1 if value else 0

    def __push_platform(self):
        from assets.models import Platform

        platforms = []
        for p in Platform.objects.all():
            protocols = []
            for sp in p.protocols.all():
                protocols.append({
                    'id': str(sp.id), 'name': sp.name, 'port': sp.port,
                    'primary': self._num(sp.primary), 'required': self._num(sp.required),
                    'default': self._num(sp.default), 'public': self._num(sp.public), 'setting': sp.setting
                })
            platforms.append({
                'id': str(p.id), 'created_by': p.created_by,
                'updated_by': p.updated_by,  'comment': p.comment,
                'date_created': self._datetime(p.date_created),
                'date_updated': self._datetime(p.date_updated),
                'name': p.name, 'category': p.category,
                'type': p.type, 'meta': p.meta, 'internal': p.internal,
                'charset': p.charset, 'gateway_enabled': p.gateway_enabled,
                'su_enabled': p.su_enabled, 'su_method': p.su_enabled,
                'custom_fields': p.custom_fields, 'ds_enabled': p.ds_enabled,
                'protocols': protocols
            })
        data = {'resources': platforms}
        self._request(
            'POST', f'/middleman/resources/?type=platform',
            json=data, headers={'REPLICA-NAME': settings.MIDDLEMAN_SERVICE_NAME}
        )

    def __push_org(self):
        from orgs.models import Organization

        orgs = []
        for o in [Organization.system(), Organization.default()]:
            orgs.append({
                'id': self._uuid(o.id), 'created_by': o.created_by,
                'updated_by': o.updated_by, 'comment': o.comment,
                'date_created': self._datetime(o.date_created),
                'date_updated': self._datetime(o.date_updated),
                'name': o.name, 'builtin': o.builtin
            })
        data = {'resources': orgs}
        self._request(
            'POST', f'/middleman/resources/?type=org',
            json=data, headers={'REPLICA-NAME': settings.MIDDLEMAN_SERVICE_NAME}
        )

    def __push_role(self):
        from rbac.models import Role

        roles = []
        for r in Role.objects.all():
            roles.append({
                'id': self._uuid(r.id), 'created_by': r.created_by,
                'updated_by': r.updated_by, 'comment': r.comment,
                'date_created': self._datetime(r.date_created),
                'date_updated': self._datetime(r.date_updated),
                'name': r.name, 'scope': r.scope, 'builtin': r.builtin
            })
        data = {'resources': roles}
        self._request(
            'POST', f'/middleman/resources/?type=role',
            json=data, headers={'REPLICA-NAME': settings.MIDDLEMAN_SERVICE_NAME}
        )

    def __push_user(self):
        from users.models import User
        from rbac.models import RoleBinding

        users = []
        for u in User.objects.filter(username='admin'):
            role_bindings = []
            for r in RoleBinding.objects.filter(user=u):
                role_bindings.append({
                    'id': self._uuid(r.id), 'created_by': r.created_by, 'updated_by': r.updated_by,
                    'comment': r.comment, 'date_created': self._datetime(r.date_created),
                    'date_updated': self._datetime(r.date_updated), 'user_id': self._uuid(r.user_id),
                    'scope': r.scope, 'org_id': self._uuid(r.org_id), 'role_id': self._uuid(r.role_id),
                })
            users.append({
                'id': self._uuid(u.id), 'name': u.name, 'username': u.username,
                'password': u.password, 'email': u.email,
                'last_login': self._datetime(u.last_login),
                'date_joined': self._datetime(u.date_joined),
                'date_expired': self._datetime(u.date_expired),
                'date_password_last_updated': self._datetime(u.date_password_last_updated),
                'date_api_key_last_used': self._datetime(u.date_api_key_last_used),
                'first_name': u.first_name, 'last_name': u.last_name,
                'is_active': u.is_active, 'role': u.role, 'avatar': '',
                'is_service_account': u.is_service_account,
                'wechat': u.wechat, 'phone': u.phone, 'mfa_level': u.mfa_level,
                'otp_secret_key': u.otp_secret_key, 'is_first_login': u.is_first_login,
                'private_key': u.private_key, 'public_key': u.public_key,
                'created_by': u.created_by, 'updated_by': u.updated_by, 'comment': u.comment,
                'need_update_password': u.need_update_password, 'source': u.source,
                'wecom_id': u.wecom_id, 'dingtalk_id': u.dingtalk_id, 'feishu_id': u.feishu_id,
                'lark_id': u.lark_id, 'slack_id': u.slack_id, 'face_vector': u.face_vector,
                'date_updated': self._datetime(u.date_updated),
                'role_bindings': role_bindings,
            })
        data = {'resources': users}
        self._request(
            'POST', f'/middleman/resources/?type=user',
            json=data, headers={'REPLICA-NAME': settings.MIDDLEMAN_SERVICE_NAME}
        )

    def __push_node(self):
        # TODO 这里先同步 default 节点，后续每次都要推送各个组织跟节点
        from assets.models import Node

        for n in [Node.default_node()]:
            nodes = [{
                'id': self._uuid(n.id), 'created_by': n.created_by, 'updated_by': n.updated_by,
                'comment': n.comment, 'date_created': self._datetime(n.date_created),
                'date_updated': self._datetime(n.date_updated), 'value': n.value,
                'key': n.key, 'org_id': self._uuid(n.org_id, replace=False), 'full_value': n.full_value,
                'child_mark': n.child_mark, 'date_create': self._datetime(n.date_create),
                'parent_key': n.parent_key, 'assets_amount': n.assets_amount,
            }]
        data = {'resources': nodes}
        self._request(
            'POST', f'/middleman/resources/?type=node',
            json=data, headers={'REPLICA-NAME': settings.MIDDLEMAN_SERVICE_NAME}
        )

    def __push_some_resource(self):
        # TODO (后续异步处理)这里要推送一些初始化的数据给middleman，不然可能数据就对不上了，比如角色，平台
        self.__push_platform()
        self.__push_org()
        self.__push_role()
        self.__push_user()
        self.__push_node()

    def _register(self):
        lock_key = 'middleman:register:lock'

        if not cache.add(lock_key, 'locking', 10):
            logger.info('Another process is registering middleman, skip')
            return

        try:
            self.__register()
            self.__push_some_resource()
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
