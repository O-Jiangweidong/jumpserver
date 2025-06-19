# -*- coding: utf-8 -*-
#
import uuid

from django.http import Http404
from rest_framework.response import Response

from common.exceptions import JMSException
from common.utils import middleman_client, pk2id
from common.mixins.middleman import MiddlemanMixin
from orgs.mixins.api import OrgBulkModelViewSet
from perms.filters import AssetPermissionFilter
from perms.models import AssetPermission
from perms.serializers import (
    AssetPermissionSerializer, AssetPermissionListSerializer,
    ActionChoicesField,
)


__all__ = ['AssetPermissionViewSet']


class AssetPermissionViewSet(MiddlemanMixin, OrgBulkModelViewSet):
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
    tp = 'permission'

    @staticmethod
    def _build_data(request, serializer, id_=None):
        current_username = request.user.username
        raw_data = serializer.data
        validated_data = serializer.validated_data
        data = {
            'id': id_ or validated_data.get('id', str(uuid.uuid4())),
            'name': validated_data['name'],
            'comment': validated_data.get('comment', ''),
            'is_active': validated_data.get('is_active', False),
            'date_start': str(validated_data.get('date_start', '')),
            'date_expired': str(validated_data.get('date_expired', '')),
            'created_by': current_username,
            'updated_by': current_username,
            'user_ids': pk2id(validated_data.get('users', [])),
            'user_group_ids': pk2id(validated_data.get('user_groups', [])),
            'asset_ids': pk2id(validated_data.get('assets', [])),
            'node_ids': pk2id(validated_data.get('nodes', [])),
            'accounts': validated_data.get('accounts', []),
            'protocols': validated_data.get('protocols', []),
            'actions': validated_data.get('actions', 127),
            'actions_display': [a['value'] for a in raw_data.get('actions', [])]
        }
        return data

    def update(self, request, *args, **kwargs):
        id_ = kwargs.get('pk', '')
        if self.has_middleman_master_behavior():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = self._build_data(request, serializer, id_)
            resp = middleman_client.update_resource(
                type_='perm', id_=id_, data=data, slave_name=self.slave_name
            )
            return Response(status=resp.status_code, data=resp.json())
        elif self.is_middleman_slave():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = self._build_data(request, serializer, id_)
            resp = middleman_client.update_resource(
                type_='perm', id_=id_, data=data, slave_name=self.slave_name
            )
            resp.raise_for_status()
            return super().update(request, *args, **kwargs)
        else:
            return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        if self.has_middleman_master_behavior():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_='perm', data=[data], slave_name=self.slave_name
            )
            resp.raise_for_status()
        elif self.is_middleman_slave():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_='perm', data=[data], slave_name=self.slave_name
            )
            resp.raise_for_status()
            self.perform_create(serializer)
        else:
            self.perform_create(serializer)

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.action in ('create', 'update') and self.has_middleman_master_behavior():
            serializer = self._clean_serializer_fields(serializer)
        return serializer

    def retrieve(self, request, *args, **kwargs):
        id_ = kwargs.get('pk', '')
        if self.has_middleman_master_behavior():
            resp = middleman_client.get_perms(
                slave_name=self.slave_name, query_params={'id': id_}
            )
            resp.raise_for_status()
            permissions = []
            for perm in resp.get('results', [])[:1]:
                perm['actions'] = ActionChoicesField().to_representation(perm['actions'])
                permissions.append(perm)
            return Response(permissions[0] if len(permissions) else {})
        else:
            return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
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
