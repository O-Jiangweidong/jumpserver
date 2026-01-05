import os
import json

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import status as http_status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny

from assets.models import Node
from common import serializers
from common.utils import get_logger, GMSM4EcbCrypto, lazyproperty
from orgs.api import org_related_models
from orgs.models import Organization
from orgs.utils import tmp_to_root_org
from users.models import User
from rbac.models import RoleBinding, Role


logger = get_logger(__name__)


__all__ = [
    'CustomSchemaService',
    'CustomCreateOrg', 'CustomUpdateOrg', 'CustomDeleteOrg',
    'CustomCreateUser', 'CustomUpdateUser', 'CustomDeleteUser',
]


class BaseCustomAPIView(GenericAPIView):
    permission_classes = (AllowAny,)
    override_response = False

    def perform_authentication(self, request):
        username = request.data.get('bimRemoteUser', '')
        password = request.data.get('bimRemotePwd', '')
        bim_username = os.environ.get('bimUsername', 'bim')
        if not username or not password or username != bim_username:
            raise AuthenticationFailed()

        user = User.objects.filter(username=username).first()
        if not user:
            raise AuthenticationFailed()

        if not user.check_password(password):
            raise AuthenticationFailed()

        request.user = user

    @lazyproperty
    def crypto(self):
        if not settings.CUSTOM_API_SECRET_KEY:
            logger.warning('CUSTOM_API_SECRET_KEY is not set')
            return None

        return GMSM4EcbCrypto(settings.CUSTOM_API_SECRET_KEY)

    def initial(self, request, *args, **kwargs):
        if request.method != 'POST' or self.crypto is None:
            super().initial(request, *args, **kwargs)
            return

        encrypted_body = request.body
        try:
            decrypted_data = json.loads(self.crypto._decrypt(encrypted_body))
        except Exception as e:
            logger.error('{} decryption failed {}'.format(encrypted_body, e))
            decrypted_data = {}

        request._full_data = decrypted_data
        super().initial(request, *args, **kwargs)

    def api_handle(self, serializer):
        return {}

    def post(self, request, *args, **kwargs):
        bid = request.data.get('bimRequestId', '')
        response_data = {'bimRequestId': bid, 'resultCode': '0', 'message': 'success'}
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            api_data = self.api_handle(serializer)
            if self.override_response:
                response_data = api_data
            else:
                response_data.update(api_data)
            status = http_status.HTTP_200_OK
        except Exception as e:
            status = http_status.HTTP_400_BAD_REQUEST
            response_data.update({'resultCode': '500', 'message': str(e)})

        encode_data = json.dumps(response_data).encode('utf-8')
        from django.http import HttpResponse
        return HttpResponse(
            content=self.crypto._encrypt(encode_data), status=status,
            content_type='application/octet-stream',
        )


class CustomSchemaService(BaseCustomAPIView):
    override_response = True
    serializer_class = serializers.SchemaServiceSerializer

    def api_handle(self, serializer):
        return serializer.data


class CustomCreateOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgCreateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        org = Organization.objects.fitler(name=data['name']).first()
        if org:
            raise ValueError(_('Name already exists'))
        try:
            org = Organization.objects.create(
                id=data['id'], name=data['name'], comment=data['comment'],
            )
        except Exception as e:
            raise ValueError(e)
        return {'uid': str(org.id)}


class CustomUpdateOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgUpdateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        org = Organization.objects.fitler(id=data['bimOrgId']).first()
        if not org:
            raise ValueError(_('%s object does not exist.') % data['bimOrgId'])

        org.name = data['name']
        org.comment = data['comment']
        try:
            org.save(update_fields=['name', 'comment'])
        except Exception as e:
            raise ValueError(e)
        return {}


class CustomDeleteOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgDeleteSerializer

    @tmp_to_root_org()
    def get_data_from_model(self, org, model):
        if model == User:
            data = model.get_org_users(org=org)
        elif model == Node:
            data = model.objects.filter(org_id=org.id).exclude(parent_key='', key__regex=r'^[0-9]+$')
        else:
            data = model.objects.filter(org_id=org.id)
        return data

    def delete_org(self, org):
        if str(org.id) in settings.AUTH_LDAP_SYNC_ORG_IDS:
            msg = _(
                'LDAP synchronization is set to the current organization. '
                'Please switch to another organization before deleting'
            )
            raise ValueError(detail=msg)

        for model in org_related_models:
            data = self.get_data_from_model(org, model)
            if not data:
                continue
            msg = _(
                'The organization have resource ({}) cannot be deleted'
            ).format(model._meta.verbose_name)
            raise ValueError(detail=msg)

        org.delete()

    def api_handle(self, serializer):
        data = serializer.validated_data
        org = Organization.objects.fitler(id=data['bimOrgId']).first()
        if not org:
            raise ValueError(_('%s object does not exist.') % data['bimOrgId'])

        try:
            self.delete_org(org)
        except Exception as e:
            raise ValueError(e)
        return {}


class CustomCreateUser(BaseCustomAPIView):
    serializer_class = serializers.UserCreateSerializer

    @staticmethod
    def raise_unique_error(field_name):
        model_name = User.Meta.verbose_name
        msg = _('%(model_name)s with this %(field_label)s already exists.')
        raise ValueError(msg % {'model_name': model_name, 'field_label': field_name})

    def api_handle(self, serializer):
        data = serializer.validated_data
        username, name, email = data['username'], data['name'], data['email']
        if User.objects.filter(username=username).exists():
            self.raise_unique_error(_('Username'))
        if User.objects.filter(username=name).exists():
            self.raise_unique_error(_('Name'))
        if User.objects.filter(username=email).exists():
            self.raise_unique_error(_('Email'))

        org = Organization.objects.filter(id=data['org_id']).first()
        if not org:
            org = Organization.default()

        try:
            user = User.objects.create(
                id=data['id'], name=data['name'], username=data['username'],
                email=data['email'], is_active=data['is_active'],
                mfa_level=data['mfa_level'], phone=data['phone'],
                date_expired=data['date_expired'], comment=data['comment'],
            )
            org_user_role = Role.BuiltinRole.org_user.get_role()
            RoleBinding.objects.create(user=user, role=org_user_role, org=org, scope='org')
        except Exception as e:
            raise ValueError(e)
        return {'uid': str(user.id)}


class CustomUpdateUser(BaseCustomAPIView):
    serializer_class = serializers.UserUpdateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        user = User.objects.fitler(id=data['bimUid']).first()
        if not user:
            raise ValueError(_('%s object does not exist.') % data['bimUid'])

        update_fields = [
            'name', 'username', 'email', 'is_active', 'mfa_level',
            'phone', 'date_expired', 'comment'
        ]

        for f in update_fields:
            setattr(user, f, data[f])
        try:
            user.save(update_fields=update_fields)
        except Exception as e:
            raise ValueError(e)
        return {}


class CustomDeleteUser(BaseCustomAPIView):
    serializer_class = serializers.UserDeleteSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        user = User.objects.fitler(id=data['bimUid']).first()
        if not user:
            raise ValueError(_('%s object does not exist.') % data['bimUid'])

        try:
            user.delete()
        except Exception as e:
            raise ValueError(e)
        return {}
