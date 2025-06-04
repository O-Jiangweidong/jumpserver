import urllib.parse

import requests

from django.conf import settings

from common.utils import lazyproperty, get_logger


logger = get_logger(__name__)


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
        logger.debug('Request url: %s' % url)
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

    def get_assets(self, m_type='asset', slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type={m_type}'
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

    def get_accounts(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=account'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def get_perms(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=perm'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def get_children_nodes(self, slave_name='', query_params=None, **kwargs):
        url = f'/middleman/resources/?m_type=children_node'
        resp = self._request(
            'GET', url, headers={'SLAVE-NAME': slave_name},
            query_params=query_params, **kwargs
        )
        return resp.json()

    def delete_instance(self, tp, id_, slave_name=''):
        # TODO 后续这里是异步任务，如果任务失败了，要有重试机制
        url = f'/middleman/resources/{id_}/?m_type={tp}'
        return self._request(
            'DELETE', url, headers={'SLAVE-NAME': slave_name},
        )

    def post_resource(self, type_, data, slave_name, **kwargs):
        # TODO 后续这里是异步任务，如果任务失败了，要有重试机制
        if not self.enable:
            return

        return self._request(
            'POST', f'/middleman/resources/?m_type={type_}',
            json=data, headers={'SLAVE-NAME': slave_name}
        )

    def update_resource(self, type_, id_, data, slave_name, **kwargs):
        if not self.enable:
            return

        return self._request(
            'PATCH', f'/middleman/resources/{id_}/?m_type={type_}',
            json=data, headers={'SLAVE-NAME': slave_name}
        )


middleman_client = MiddlemanClient()
