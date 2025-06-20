# ~*~ coding: utf-8 ~*~
import uuid

from collections import defaultdict

from django.utils.translation import gettext as _
from django.http import Http404
from rest_framework import generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_bulk import BulkModelViewSet

from common.api import CommonApiMixin, SuggestionMixin
from common.exceptions import JMSException
from common.drf.filters import AttrRulesFilterBackend
from common.utils import get_logger, middleman_client
from common.mixins.middleman import MiddlemanMixin
from orgs.utils import current_org, tmp_to_root_org
from rbac.models import Role, RoleBinding
from rbac.permissions import RBACPermission
from users.utils import LoginBlockUtil, MFABlockUtils
from .mixins import UserQuerysetMixin
from .. import serializers
from ..exceptions import UnableToDeleteAllUsers
from ..filters import UserFilter
from ..models import User
from ..notifications import ResetMFAMsg
from ..permissions import UserObjectPermission
from ..serializers import (
    UserSerializer, MiniUserSerializer, InviteSerializer, UserRetrieveSerializer
)
from ..signals import post_user_create

logger = get_logger(__name__)
__all__ = [
    'UserViewSet', 'UserChangePasswordApi',
    'UserUnblockPKApi', 'UserResetMFAApi',
]


class UserViewSet(
    MiddlemanMixin, CommonApiMixin, UserQuerysetMixin,
    SuggestionMixin, BulkModelViewSet
):
    filterset_class = UserFilter
    extra_filter_backends = [AttrRulesFilterBackend]
    search_fields = ('username', 'email', 'name')
    permission_classes = [RBACPermission, UserObjectPermission]
    serializer_classes = {
        'default': UserSerializer,
        'suggestion': MiniUserSerializer,
        'invite': InviteSerializer,
        'retrieve': UserRetrieveSerializer,
    }
    rbac_perms = {
        'match': 'users.match_user',
        'invite': 'users.invite_user',
        'remove': 'users.remove_user',
        'bulk_remove': 'users.remove_user',
    }
    tp = 'user'

    @staticmethod
    def _build_data(request, serializer):
        current_username = request.user.username
        validated_data = serializer.validated_data
        return {
            'id': validated_data.get('id', str(uuid.uuid4())),
            'is_first_login': True,
            'name': validated_data['name'],
            'username': validated_data['username'],
            'email': validated_data['email'],
            'wechat': validated_data.get('wechat', ''),
            'phone': validated_data.get('phone', ''),
            'mfa_level': validated_data['mfa_level'],
            'source': validated_data['source'],
            'comment': validated_data.get('comment', ''),
            'is_active': validated_data.get('is_active', False),
            'need_update_password': validated_data.get('need_update_password', True),
            'date_expired': str(validated_data.get('date_expired', '')),
            'password': validated_data.get('password_raw'),
            'password_strategy': serializer.initial_data.get('password_strategy', 'email'),
            'created_by': current_username,
            'updated_by': current_username,
            'groups': [{'id': g.get('pk') or g.get('id', '')} for g in validated_data.get('groups', [])],
            'roles': validated_data.get('system_roles', []) + validated_data.get('org_roles', []),
        }

    def perform_create(self, serializer):
        if self.has_middleman_master_behavior():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_='user', data=[data], slave_name=self.slave_name
            )
            resp.raise_for_status()
        elif self.is_middleman_slave() and not self.from_middleman():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_='user', data=[data], slave_name=self.slave_name
            )
            resp.raise_for_status()
            self.custom_perform_create(serializer)
        else:
            self.custom_perform_create(serializer)

    def list(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return super().list(request, *args, **kwargs)

        resp = middleman_client.get_users(
            slave_name=self.slave_name, query_params=dict(request.query_params.items())
        )
        return Response(resp)

    def allow_bulk_destroy(self, qs, filtered):
        is_valid = filtered.count() < qs.count()
        if not is_valid:
            raise UnableToDeleteAllUsers()
        return True

    @action(methods=['get'], detail=False, url_path='suggestions')
    def match(self, request, *args, **kwargs):
        with tmp_to_root_org():
            return super().match(request, *args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        """重写 get_serializer, 用于设置用户的角色缓存
        放到 paginate_queryset 里面会导致 导出有问题, 因为导出的时候，没有 pager
        """
        if len(args) == 1 and kwargs.get('many'):
            queryset = self.set_users_roles_for_cache(args[0])
            queryset = self.set_users_orgs_roles(args[0])
            args = (queryset,)
        serializer = super().get_serializer(*args, **kwargs)
        if self.action == 'create' and self.has_middleman_master_behavior():
            serializer = self._clean_serializer_fields(serializer)
        return serializer

    @staticmethod
    def set_users_roles_for_cache(queryset):
        # Todo: 未来有机会用 SQL 实现
        queryset_list = queryset
        user_ids = [u.id for u in queryset_list]
        role_bindings = RoleBinding.objects.filter(user__in=user_ids) \
            .values('user_id', 'role_id', 'scope')

        role_mapper = {r.id: r for r in Role.objects.all()}
        user_org_role_mapper = defaultdict(set)
        user_system_role_mapper = defaultdict(set)

        for binding in role_bindings:
            role_id = binding['role_id']
            user_id = binding['user_id']
            if binding['scope'] == RoleBinding.Scope.system:
                user_system_role_mapper[user_id].add(role_mapper[role_id])
            else:
                user_org_role_mapper[user_id].add(role_mapper[role_id])

        for u in queryset_list:
            system_roles = user_system_role_mapper[u.id]
            org_roles = user_org_role_mapper[u.id]
            u.org_roles.cache_set(org_roles)
            u.system_roles.cache_set(system_roles)
        return queryset_list

    @staticmethod
    def set_users_orgs_roles(queryset):
        user_ids = [u.id for u in queryset]
        rbs = RoleBinding.objects_raw.filter(
            user__in=user_ids, scope='org'
        ).prefetch_related('user', 'role', 'org')
        user_rbs_mapper = defaultdict(set)
        for rb in rbs:
            user_rbs_mapper[rb.user_id].add(rb)

        for u in queryset:
            user_rbs = user_rbs_mapper[u.id]
            orgs_roles = defaultdict(set)
            for rb in user_rbs:
                orgs_roles[rb.org_name].add(rb.role.display_name)
            setattr(u, 'orgs_roles', orgs_roles)
        return queryset

    def custom_perform_create(self, serializer):
        users = serializer.save()
        if isinstance(users, User):
            users = [users]
        self.send_created_signal(users)

    def perform_bulk_update(self, serializer):
        user_ids = [
            d.get("id") or d.get("pk") for d in serializer.validated_data
        ]
        users = current_org.get_members().filter(id__in=user_ids)
        for user in users:
            self.check_object_permissions(self.request, user)
        return super().perform_bulk_update(serializer)

    def perform_bulk_destroy(self, objects):
        for obj in objects:
            self.check_object_permissions(self.request, obj)
            self.perform_destroy(obj)

    @action(methods=['post'], detail=False)
    def invite(self, request):
        if not current_org or current_org.is_root():
            error = {"error": "Not a valid org"}
            return Response(error, status=400)

        serializer_cls = self.get_serializer_class()
        serializer = serializer_cls(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        users = validated_data['users']
        org_roles = validated_data['org_roles']
        has_self = any([str(u.id) == str(request.user.id) for u in users])
        if has_self and not request.user.is_superuser:
            error = {"error": _("Can not invite self")}
            return Response(error, status=400)
        for user in users:
            user.org_roles.set(org_roles)
        return Response(serializer.data, status=201)

    @action(methods=['post'], detail=True)
    def remove(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.remove()
        return Response(status=204)

    @action(methods=['post'], detail=False, url_path='remove')
    def bulk_remove(self, request, *args, **kwargs):
        qs = self.get_queryset()
        filtered = self.filter_queryset(qs)

        for instance in filtered:
            instance.remove()
        return Response(status=204)

    def send_created_signal(self, users):
        if not isinstance(users, list):
            users = [users]
        for user in users:
            post_user_create.send(self.__class__, user=user)


class UserChangePasswordApi(UserQuerysetMixin, generics.UpdateAPIView):
    serializer_class = serializers.ChangeUserPasswordSerializer

    def perform_update(self, serializer):
        user = self.get_object()
        user.password_raw = serializer.validated_data["password"]
        user.save()


class UserUnblockPKApi(MiddlemanMixin, UserQuerysetMixin, generics.UpdateAPIView):
    serializer_class = serializers.UserSerializer

    def update(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return super().update(request, *args, **kwargs)

        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404

        resp = middleman_client.update_resource(
            type_='user_unblock', id_=id_, slave_name=self.slave_name
        )
        if resp.status_code > 300:
            raise JMSException(resp.json())
        return Response(status=200)

    def perform_update(self, serializer):
        user = self.get_object()
        username = user.username if user else ''
        LoginBlockUtil.unblock_user(username)
        MFABlockUtils.unblock_user(username)


class UserResetMFAApi(MiddlemanMixin, UserQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = serializers.ResetOTPSerializer

    def raw_retrieve(self, request, *args, **kwargs):
        user = self.get_object() if kwargs.get('pk') else request.user
        if user == request.user:
            msg = _("Could not reset self otp, use profile reset instead")
            return Response({"error": msg}, status=400)

        backends = user.active_mfa_backends_mapper
        for backend in backends.values():
            if backend.can_disable():
                backend.disable()

        ResetMFAMsg(user).publish_async()
        return Response({"msg": "success"})

    def retrieve(self, request, *args, **kwargs):
        if not self.has_middleman_master_behavior():
            return self.raw_retrieve(request, *args, **kwargs)

        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404

        resp = middleman_client.update_resource(
            type_='user_reset_mfa', id_=id_, slave_name=self.slave_name
        )
        if resp.status_code > 300:
            raise JMSException(resp.json())
        return Response(status=200)
