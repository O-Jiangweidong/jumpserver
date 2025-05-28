import json

import requests

from django.conf import settings
from rest_framework.utils.encoders import JSONEncoder

from common.utils import lazyproperty


class MiddlemanClient(object):
    def __init__(self):
        self.endpoint = settings.MIDDLEMAN_ENDPOINT

    @lazyproperty
    def _auth_token(self):
        return f'Bearer {settings.MIDDLEMAN_AUTH_TOKEN}'

    def _request(self, method, url, **kwargs):
        url = self.endpoint + url
        kwargs.setdefault('headers', {})
        kwargs['headers']['Authorization'] = self._auth_token
        return requests.request(method, url, **kwargs)

    @property
    def enable(self):
        return bool(settings.MIDDLEMAN_ENDPOINT)

    def get_index(self, **kwargs):
        count = self.get_slave_nodes().get('total', 0)
        return {'total_count_slave_node': count}

    def get_slave_nodes(self, **kwargs):
        url = '/middleman/slave-nodes/'
        resp = self._request('GET', url)
        return resp.json()

    def get_users(self, limit=100, offset=0, slave_name='', search='', **kwargs):
        url = f'/middleman/resources/?type=user&limit={limit}&offset={offset}'
        if search:
            url += f'&search={search}'
        resp = self._request('GET', url, headers={'SLAVE-NAME': slave_name})
        return resp.json()

    def get_roles(self, slave_name='', scope='', **kwargs):
        url = f'/middleman/resources/?type=role&scope={scope}'
        resp = self._request('GET', url, headers={'SLAVE-NAME': slave_name})
        return resp.json()

    def get_assets(self, limit=100, offset=0, slave_name='', **kwargs):
        url = f'/middleman/resources/?type=asset&limit={limit}&offset={offset}'
        resp = self._request('GET', url, headers={'SLAVE-NAME': slave_name})
        return resp.json()

    def get_platforms(self, limit=100, offset=0, slave_name='', **kwargs):
        url = f'/middleman/resources/?type=platform&limit={limit}&offset={offset}'
        resp = self._request('GET', url, headers={'SLAVE-NAME': slave_name})
        return resp.json()

    def post_resource(self, type_, data, slave_name, **kwargs):
        # TODO 后续这里是异步任务，如果任务失败了，要有重试机制
        if not self.enable:
            return

        return self._request(
            'POST', f'/middleman/resources/?type={type_}',
            json=data, headers={'SLAVE-NAME': slave_name}
        )


middleman_client = MiddlemanClient()
