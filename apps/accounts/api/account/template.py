import uuid

from django_filters import rest_framework as drf_filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts import serializers
from accounts.const.automation import DEFAULT_PASSWORD_RULES
from accounts.mixins import AccountRecordViewLogMixin
from accounts.models import AccountTemplate
from accounts.tasks import template_sync_related_accounts
from assets.const import Protocol
from authentication.permissions import UserConfirmation, ConfirmType
from common.drf.filters import BaseFilterSet
from common.mixins.middleman import MiddlemanMixin
from common.utils import middleman_client
from orgs.mixins.api import OrgBulkModelViewSet
from rbac.permissions import RBACPermission


class AccountTemplateFilterSet(BaseFilterSet):
    protocols = drf_filters.CharFilter(method='filter_protocols')

    class Meta:
        model = AccountTemplate
        fields = ('username', 'name')

    @staticmethod
    def filter_protocols(queryset, name, value):
        secret_types = set()
        protocols = value.split(',')
        protocol_secret_type_map = Protocol.settings()
        for p in protocols:
            if p not in protocol_secret_type_map:
                continue
            _st = protocol_secret_type_map[p].get('secret_types', [])
            secret_types.update(_st)
        if not secret_types:
            secret_types = ['password']
        queryset = queryset.filter(secret_type__in=secret_types)
        return queryset


class AccountTemplateViewSet(MiddlemanMixin, OrgBulkModelViewSet):
    model = AccountTemplate
    filterset_class = AccountTemplateFilterSet
    search_fields = ('username', 'name')
    serializer_classes = {
        'default': serializers.AccountTemplateSerializer,
    }
    rbac_perms = {
        'su_from_account_templates': 'accounts.view_accounttemplate',
        'sync_related_accounts': 'accounts.change_account',
    }
    use_middleman_retrieve = False
    use_middleman_update = False
    tp = 'account_template'

    @staticmethod
    def _build_data(request, serializer, id_=None, is_create=True):
        current_username = request.user.username
        validated_data = serializer.validated_data
        data = {
            'name': validated_data['name'],
            'username': validated_data.get('username', ''),
            'secret': validated_data.get('secret', ''),
            'privileged': validated_data.get('privileged', False),
            'auto_push': validated_data.get('auto_push', False),
            'secret_type': validated_data.get('secret_type', 'password'),
            'secret_strategy': validated_data.get('secret_strategy', 'specific'),
            'password_rules': validated_data.get('password_rules', DEFAULT_PASSWORD_RULES),
            'comment': validated_data.get('comment', ''),
        }
        if is_create:
            data.update({
                'id': id_ or validated_data.get('id', str(uuid.uuid4())),
                'created_by': current_username,
            })
        return data

    def list(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return super().list(request, *args, **kwargs)

        resp = middleman_client.get_account_templates(
            slave_name=self.slave_name, query_params=dict(request.query_params.items())
        )
        return Response(resp)

    @action(methods=['get'], detail=False, url_path='su-from-account-templates')
    def su_from_account_templates(self, request, *args, **kwargs):
        pk = request.query_params.get('template_id')
        templates = AccountTemplate.get_su_from_account_templates(pk)
        templates = self.filter_queryset(templates)
        serializer = self.get_serializer(templates, many=True)
        return Response(data=serializer.data)

    @action(methods=['patch'], detail=True, url_path='sync-related-accounts')
    def sync_related_accounts(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = str(request.user.id)
        task = template_sync_related_accounts.delay(str(instance.id), user_id)
        return Response({'task': task.id}, status=status.HTTP_200_OK)


class AccountTemplateSecretsViewSet(AccountRecordViewLogMixin, AccountTemplateViewSet):
    serializer_classes = {
        'default': serializers.AccountTemplateSecretSerializer,
    }
    http_method_names = ['get', 'options']
    permission_classes = [RBACPermission, UserConfirmation.require(ConfirmType.MFA)]
    rbac_perms = {
        'list': 'accounts.view_accounttemplatesecret',
        'retrieve': 'accounts.view_accounttemplatesecret',
    }
