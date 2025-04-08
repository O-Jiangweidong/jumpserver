import os
import re

import thriftpy2

from thriftpy2.rpc import make_client
from django.conf import settings

from common.utils import get_logger


logger = get_logger(__file__)


class Client(object):
    OK = 'ok'

    @property
    def client(self):
        return self._get_client()

    def _get_client(self):
        thrift_path = os.path.join(settings.BASE_DIR, 'assets', 'rpc', 'sync2.thrift')
        sync_thrift2 = thriftpy2.load(thrift_path, module_name='sync_thrift')
        return make_client(sync_thrift2.VPNRPCService, *self.get_vpn_address())

    @staticmethod
    def get_vpn_address():
        error = 'VPN_RPC_ADDRESS is invalid.'
        ip_port_list = str(settings.VPN_RPC_ADDRESS).split(":")
        if len(ip_port_list) != 2:
            raise Exception(error)
        ip_addr, port = ip_port_list
        # 检查 IP 地址是否合法
        if not re.match(r"^(\d{1,3}\.){3}\d{1,3}$", ip_addr):
            raise Exception(error)
        # 检查端口号是否合法
        try:
            port = int(port)
            if not (0 < port < 65536):
                Exception(error)
        except ValueError:
            Exception(error)
        return ip_addr, port

    def query_asset(self, assets):
        assets_map = {a.ip: a for a in assets}
        ok_assets, fail_assets, error = [], [], False
        query_ips = assets_map.keys()
        if not query_ips:
            return ok_assets, fail_assets, error
        result = self.client.query(';'.join(query_ips))
        if str(result.code) != '0':
            fail_assets.extend(query_ips)
            logger.error('Sync asset error: %s' % result.msg)
            return ok_assets, fail_assets, error

        for item in result.data:
            asset = assets_map.get(item.ip)
            if not asset:
                continue
            if item.status == self.OK:
                ok_assets.append(asset.id)
            else:
                fail_assets.append(asset.id)
        return ok_assets, fail_assets, error

    def sync_asset(self, assets):
        assets_map = {a.ip: a for a in assets}
        action = 'create' if len(assets_map) == 1 else 'all'
        query_ips = assets_map.keys()
        if not query_ips:
            return False, 'No assets select.'
        result = self.client.synchronize(action, ';'.join(query_ips))
        logger.info(f'Rpc client response: {result}')
        return str(result.code).strip() == '0', result.msg


client = Client()
