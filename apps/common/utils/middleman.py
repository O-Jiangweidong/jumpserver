import requests

from django.conf import settings

from common.utils.encode import data_to_json
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

    def get_slave_nodes(self):
        url = '/middleman/slave-nodes/'
        resp = self._request('GET', url)
        return resp.json()

    def get_users(self, limit=100, offset=0, slave_name='', **kwargs):
        url = f'/middleman/resources/?type=user&limit={limit}&offset={offset}'
        resp = self._request('GET', url, headers={'SLAVE-NAME': slave_name})
        return resp.json()

    def post_resource(self, data):
        if not self.enable:
            return

        self._request('POST', '/middleman/resources/', json=data)


middleman_client = MiddlemanClient()
