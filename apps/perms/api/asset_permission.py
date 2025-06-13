# -*- coding: utf-8 -*-
#
import uuid

from django.http import Http404
from rest_framework.response import Response

from common.exceptions import JMSException
from common.utils import middleman_client, pk2id
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

    @staticmethod
    def _build_data(request, raw_d, d, id_=None):
        cur_username = request.user.username
        data = {
            'id': id_ or d.get('id', str(uuid.uuid4())),
            'name': d['name'], 'comment': d.get('comment', ''),
            'is_active': d.get('is_active', False),
            'date_start': str(d.get('date_start', '')),
            'date_expired': str(d.get('date_expired', '')),
            'created_by': cur_username, 'updated_by': cur_username,
            'user_ids': pk2id(d.get('users', [])),
            'user_group_ids': pk2id(d.get('user_groups', [])),
            'asset_ids': pk2id(d.get('assets', [])),
            'node_ids': pk2id(d.get('nodes', [])),
            'accounts': d.get('accounts', []),
            'protocols': d.get('protocols', []),
            'actions': d.get('actions', 127),
            'actions_display': [a['value'] for a in raw_d.get('actions', [])]
        }
        return data

    def update(self, request, *args, **kwargs):
        if not self.is_middleman_master():
            return super().update(request, *args, **kwargs)

        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = self._build_data(request, serializer.data, serializer.validated_data, id_)
        resp = middleman_client.update_resource(
            type_='perm', id_=id_, data=data, slave_name=self.slave_name
        )
        return Response(status=resp.status_code, data=resp.json())

    def perform_create(self, serializer):
        if not self.is_middleman_master():
            return super().perform_create(serializer)

        data = self._build_data(self.request, serializer.data, serializer.validated_data)
        middleman_client.post_resource(
            type_='perm', data=[data], slave_name=self.slave_name
        )

    def destroy(self, request, *args, **kwargs):
        if not self.is_middleman_master():
            return super().destroy(request, *args, **kwargs)

        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404
        resp = middleman_client.delete_instance(
            tp='perm', id_=id_, slave_name=self.slave_name
        )
        return Response(status=resp.status_code, data=resp.json())

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action in ('create', 'update') and self.is_middleman_master():
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
