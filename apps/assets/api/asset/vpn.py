from django.utils.translation import gettext_lazy as _
from rest_framework.views import Response
from rest_framework.decorators import action

from assets import serializers
from assets.rpc.client import client
from assets.models import Asset, Connectivity
from common.utils import get_logger
from orgs.mixins.api import OrgBulkModelViewSet


logger = get_logger(__file__)


class VPNViewSet(OrgBulkModelViewSet):
    model = Asset
    serializer_class = serializers.VPNSerializer
    search_fields = ('hostname', 'ip', 'connectivity')
    filterset_fields = search_fields
    ordering_fields = ('hostname',)
    ordering = ('hostname',)
    rbac_perms = {
        'GET': '*',
        'verify_account': '*'
    }

    def paginate_queryset(self, queryset):
        qs = super().paginate_queryset(queryset)
        try:
            ok_qs, fail_qs, _ = client.query_asset(qs)
            Asset.bulk_set_connectivity(ok_qs, Connectivity.OK, 'vpn')
            Asset.bulk_set_connectivity(fail_qs, Connectivity.ERR, 'vpn')
            for a in qs:
                if a.id in ok_qs:
                    a.vpn_connectivity = Connectivity.OK
                else:
                    a.vpn_connectivity = Connectivity.ERR
        except Exception as error:
            logger.error('RPC client error: ', error)
        return qs

    def task_sync(self, ips):
        ok = False
        if not ips:
            assets = self.get_queryset()
        else:
            assets = self.get_queryset().filter(ip__in=ips)
        try:
            ok, msg = client.sync_asset(assets)
        except Exception as error:
            logger.error('Task sync error: %s' % error)
            msg = error
        if not ok:
            response = Response(data={'error': str(msg)}, status=400)
        else:
            response = Response(data={'message': str(msg)}, status=200)
        return response

    @action(methods=['POST'], detail=False, url_path='tasks')
    def verify_account(self, request, *args, **kwargs):
        action_params = ('sync',)
        task_type = request.data.get('action', None)
        if task_type not in action_params:
            err_info = _("The parameter 'action' must be [{}]".format(','.join(action_params)))
            return Response({"error": err_info}, status=400)
        ips = request.data.get('ips', [])
        return self.task_sync(ips)
