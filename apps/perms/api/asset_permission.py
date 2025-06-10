# -*- coding: utf-8 -*-
#
from django.http import Http404
from rest_framework.response import Response

from common.exceptions import JMSException
from common.utils import middleman_client
from common.mixins.middleman import MiddlemanSerializerMixin
from orgs.mixins.api import OrgBulkModelViewSet
from perms.filters import AssetPermissionFilter
from perms.models import AssetPermission
from perms.serializers import (
    AssetPermissionSerializer, AssetPermissionListSerializer,
    ActionChoicesField,
)


__all__ = ['AssetPermissionViewSet']


class AssetPermissionViewSet(MiddlemanSerializerMixin, OrgBulkModelViewSet):
    """
    资产授权列表的增删改查api
    """
    model = AssetPermission
    serializer_classes = {
        'default': AssetPermissionSerializer,
        'list': AssetPermissionListSerializer,
    }
    filterset_class = AssetPermissionFilter
    search_fields = ('name',)

    def destroy(self, request, *args, **kwargs):
        if not self.is_middleman_master():
            return super().destroy(request, *args, **kwargs)
        else:
            id_ = kwargs.get('pk', '')
            if not id_:
                raise Http404
            resp = middleman_client.delete_instance(
                tp='perm', id_=id_, slave_name=self.slave_name
            )
            return Response(status=resp.status_code, data=resp.json())

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action == 'create' and self.is_middleman_master():
            serializer = self._clean_serializer_fields(serializer)
        return serializer

    def retrieve(self, request, *args, **kwargs):
        if not self.is_middleman_master():
            return super().retrieve(request, *args, **kwargs)

        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404

        resp = middleman_client.get_perms(
            slave_name=self.slave_name, query_params={'id': id_}
        )
        permissions = []
        for perm in resp.get('results', [])[:1]:
            perm['actions'] = ActionChoicesField().to_representation(perm['actions'])
            permissions.append(perm)
        return Response(permissions[0] if len(permissions) else {})

    def list(self, request, *args, **kwargs):
        if not self.is_middleman_master():
            return super().list(request, *args, **kwargs)

        resp = middleman_client.get_perms(
            slave_name=self.slave_name, query_params=dict(request.query_params.items())
        )
        permissions = []
        for perm in resp.get('results', []):
            perm['actions'] = ActionChoicesField().to_representation(perm['actions'])
            permissions.append(perm)
        resp['results'] = permissions
        return Response(resp)
