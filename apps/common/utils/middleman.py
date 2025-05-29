import urllib.parse

import requests

from django.conf import settings

from common.utils import lazyproperty


class MiddlemanClient(object):
    def __init__(self):
        self.endpoint = settings.MIDDLEMAN_ENDPOINT

    @lazyproperty
    def _auth_token(self):
        return f'Bearer {settings.MIDDLEMAN_AUTH_TOKEN}'

    def _request(self, method, url, query_params=None, **kwargs):
        url = self.endpoint + url
        query_params = query_params or {}
        limit = query_params.pop('limit', 100)
        offset = query_params.pop('offset', 0)
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}limit={limit}&offset={offset}'
        if query_params:
            url = f'{url}&{urllib.parse.urlencode(query_params)}'
        kwargs.setdefault('headers', {})
        kwargs['headers']['Authorization'] = self._auth_token
        print('Request url:', url)
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

    def get_users(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=user'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def get_roles(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=role'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def get_assets(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=asset'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def get_platforms(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=platform'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
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
