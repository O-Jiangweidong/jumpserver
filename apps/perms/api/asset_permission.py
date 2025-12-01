# -*- coding: utf-8 -*-
#
import uuid

from rest_framework.response import Response

from common.utils import middleman_client, pk2id
from common.mixins.middleman import MiddlemanMixin
from orgs.mixins.api import OrgBulkModelViewSet
from orgs.models import Organization
from perms.filters import AssetPermissionFilter
from perms.models import AssetPermission
from perms.serializers import (
    AssetPermissionSerializer, AssetPermissionListSerializer,
    ActionChoicesField as ActionField,
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
    tp = 'perm'

    @staticmethod
    def _build_data(request, serializer, id_=None, is_create=True):
        current_username = request.user.username
        validated_data = serializer.validated_data
        actions_number = validated_data.get('actions', 127)
        data = {
            'name': validated_data['name'],
            'comment': validated_data.get('comment', ''),
            'is_active': validated_data.get('is_active', False),
            'date_start': str(validated_data.get('date_start', '')),
            'date_expired': str(validated_data.get('date_expired', '')),
            'updated_by': current_username,
            'users': pk2id(validated_data.get('users', []), with_id=True),
            'user_groups': pk2id(validated_data.get('user_groups', []), with_id=True),
            'assets': pk2id(validated_data.get('assets', []), with_id=True),
            'nodes': pk2id(validated_data.get('nodes', []), with_id=True),
            'accounts': validated_data.get('accounts', []),
            'protocols': validated_data.get('protocols', []),
        }
        # 后边 actions 统一下
        if is_create:
            data.update({
                'id': id_ or validated_data.get('id', str(uuid.uuid4())),
                'created_by': current_username,
                'actions': actions_number,
                'actions_display': [i['value'] for i in ActionField().to_representation(actions_number)],
            })
        else:
            data.update({
                'actions': [i['value'] for i in ActionField().to_representation(actions_number)],
                'actions_value': actions_number,
            })
        return data

    @staticmethod
    def clean_retrieve_result(perm):
        perm['actions'] = ActionField().to_representation(perm['actions'])
        return perm

    def list(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return super().list(request, *args, **kwargs)

        resp = middleman_client.get_perms(
            slave_name=self.slave_name, query_params=dict(request.query_params.items())
        )
        data = self.raise_failed_request(resp)

        def format_perm(p):
            return {**p, 'actions': ActionField().to_representation(p['actions'])}

        if isinstance(data, list):
            return Response([format_perm(perm) for perm in data])
        else:
            data['results'] = [format_perm(perm) for perm in data.get('results', [])]
            return Response(data)
