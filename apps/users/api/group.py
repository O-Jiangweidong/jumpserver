# -*- coding: utf-8 -*-
#
import uuid

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from common.mixins.middleman import MiddlemanMixin
from common.utils import middleman_client, pk2id
from orgs.mixins.api import OrgBulkModelViewSet
from ..models import UserGroup, User
from ..serializers import UserGroupSerializer, UserGroupListSerializer

__all__ = ['UserGroupViewSet']


class UserGroupViewSet(MiddlemanMixin, OrgBulkModelViewSet):
    model = UserGroup
    filterset_fields = ("name",)
    search_fields = filterset_fields
    serializer_classes = {
        'default': UserGroupSerializer,
        'list': UserGroupListSerializer,
    }
    rbac_perms = (
        ("add_all_users", "users.add_usergroup"),
    )
    tp = 'user_group'

    @staticmethod
    def _build_data(request, serializer):
        current_username = request.user.username
        validated_data = serializer.validated_data
        return {
            'id': validated_data.get('id', str(uuid.uuid4())),
            'name': validated_data['name'],
            'comment': validated_data.get('comment', ''),
            'created_by': current_username,
            'updated_by': current_username,
            'users': pk2id(validated_data.get('users', [])),
        }

    def perform_create(self, serializer):
        if self.has_middleman_master_behavior():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_=self.tp, data=[data], slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
        elif self.is_middleman_slave() and not self.from_middleman():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_=self.tp, data=[data], slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            serializer.validated_data['id'] = data['id']
            super().perform_create(serializer)
        else:
            super().perform_create(serializer)

    def list(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return super().list(request, *args, **kwargs)

        resp = middleman_client.get_user_groups(
            slave_name=self.slave_name, query_params=dict(request.query_params.items())
        )
        return Response(resp)

    @action(methods=['post'], detail=True, url_path='add-all-users')
    def add_all_users(self, request, *args, **kwargs):
        instance = self.get_object()
        users = User.get_org_users().exclude(groups__id=instance.id)
        instance.users.add(*users)
        return Response(status=status.HTTP_200_OK)
