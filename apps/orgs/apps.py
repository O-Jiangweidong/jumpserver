import sys
import os

import requests

from django.apps import AppConfig
from django.core.cache import cache
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from common.utils import get_logger, middleman_client


logger = get_logger(__name__)


class OrgsConfig(AppConfig):
    name = 'orgs'
    verbose_name = _('App organizations')

    @staticmethod
    def _register_middleman():
        from users.models import User
        from settings.models import Setting

        token = settings.BOOTSTRAP_TOKEN
        md_endpoint = settings.MIDDLEMAN_ENDPOINT
        self_endpoint = settings.MIDDLEMAN_SELF_ENDPOINT
        name = settings.MIDDLEMAN_SERVICE_NAME
        role = settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower()
        display = settings.MIDDLEMAN_SERVICE_DISPLAY
        ignore_same_name = settings.MIDDLEMAN_IGNORE_SAME_NAME
        if (not md_endpoint or
                not name or
                not self_endpoint or
                role not in ['slave', 'master']):
            logger.warning('The config of the Middleman slave node is incomplete, skipping')
            return

        access_key_path = os.path.join(settings.DATA_DIR, '.access_key')
        if os.path.exists(access_key_path):
            with open(access_key_path, 'r') as f:
                cache.set('MIDDLEMAN_AUTH_TOKEN', f.read().strip(), None)
                return

        resp = None
        user = User.get_or_create_middleman(username=name, name=display)
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
        logger.debug('Middleman register successfully, role: %s' % role)

    @staticmethod
    def __push_rbac():
        from rbac.models import Role
        from rbac.serializers import RoleSerializer

        data = []
        for d in RoleSerializer(Role.objects.all(), many=True).data:
            data.append({
                'id': d['id'], 'name': d['name'], 'scope': d['scope']['value'],
                'date_created': d['date_created'], 'date_updated': d['date_updated'],
                'created_by': d['created_by'], 'updated_by': d['updated_by'],
                'comment': d['comment'], 'builtin': d['builtin'],
            })
        resp = middleman_client.post_resource(
            'role', data, settings.MIDDLEMAN_SERVICE_NAME
        )
        print('Push rbac: ', resp)

    @staticmethod
    def __push_platforms():
        from assets.models import Platform
        from assets.serializers import PlatformSerializer

        data = []
        for d in PlatformSerializer(Platform.objects.all(), many=True).data:
            data.append({
                'id': d['id'], 'name': d['name'], 'type': d['type']['value'],
                'date_created': str(d['date_created']), 'date_updated': str(d['date_updated']),
                'created_by': d['created_by'], 'updated_by': d['updated_by'],
                'category': d['category']['value'], 'internal': d['internal'],
                'comment': d['comment'],
            })
        resp = middleman_client.post_resource(
            'platform', data, settings.MIDDLEMAN_SERVICE_NAME
        )
        print('Push platform: ', resp)

    @staticmethod
    def __push_user_groups():
        from users.models import UserGroup
        from users.serializers import MiniUserGroupSerializer

        user_groups = UserGroup.objects.all()
        resp = middleman_client.post_resource(
            'user_group', MiniUserGroupSerializer(user_groups, many=True).data,
            settings.MIDDLEMAN_SERVICE_NAME
        )
        print('Push user group: ', resp)

    @staticmethod
    def __push_nodes():
        from assets.models import Node
        from assets.serializers import NodeCreateSerializer

        __ = Node.default_node()
        nodes = Node.objects.all()
        resp = middleman_client.post_resource(
            'node', NodeCreateSerializer(nodes, many=True).data,
            settings.MIDDLEMAN_SERVICE_NAME
        )
        print('Push node: ', resp)

    @staticmethod
    def __push_admin_user():
        from users.models import User

        user = User.objects.get(username='admin')
        resp = middleman_client.post_resource(
            {
                'type': 'user',
                'data': [MiddlemanUserSerializer(user).data]
            }, settings.MIDDLEMAN_SERVICE_NAME
        )
        print(resp)

    def _push_some_resource_to_middleman(self):
        if settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower() != 'slave':
            return

        self.__push_rbac()
        # self.__push_admin_user()
        self.__push_user_groups()
        self.__push_platforms()
        self.__push_nodes()

    def ready(self):
        lock_key = 'middleman_init_lock'
        acquired = cache.add(lock_key, '1', 60)
        if acquired:
            self._register_middleman()
            self._push_some_resource_to_middleman()

        from . import signal_handlers  # noqa
        from . import tasks  # noqa
        super().ready()
