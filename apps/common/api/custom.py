import base64
import json
import os
import uuid

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from rest_framework import status as http_status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny

from common import serializers
from common.utils import get_logger, GMSM4EcbCrypto, is_uuid
from users.models import User, UserGroup

logger = get_logger(__name__)

__all__ = [
    'CustomSchemaService',
    'CustomCreateOrg', 'CustomUpdateOrg', 'CustomDeleteOrg',
    'CustomCreateUser', 'CustomUpdateUser', 'CustomDeleteUser',
]


CREATE_BY_ZHUYUN = os.environ.get('ZHUYUN_CREATE_COMMENT', '竹云创建')


class BaseCustomAPIView(GenericAPIView):
    permission_classes = (AllowAny,)
    override_response = False

    def perform_authentication(self, request):
        username = request.data.get('bimRemoteUser', '')
        password = request.data.get('bimRemotePwd', '')
        bim_username = os.environ.get('bimUsername', 'bim')
        logger.debug('[ZHUYUN] Request body: %s', request.data)
        if not username or not password:
            logger.warning(f'[ZHUYUN] Missing bimRemoteUser or bimRemotePwd')
            raise AuthenticationFailed()

        if username != bim_username:
            logger.warning(f'[ZHUYUN] Invalid username: {username}, expected: {bim_username}')
            raise AuthenticationFailed()

        user = User.objects.filter(username=username).first()
        if not user:
            logger.error(f'[ZHUYUN] User {username} does not exist in the system')
            raise AuthenticationFailed()

        if not user.check_password(password):
            logger.warning(f'[ZHUYUN] Incorrect password for user {username}')
            raise AuthenticationFailed()

        request.user = user
        logger.debug(f'[ZHUYUN] User {username} authenticated successfully')

    @staticmethod
    def get_crypto():
        secret_key = os.environ.get('CUSTOM_API_SECRET_KEY')
        if not secret_key:
            logger.warning('[ZHUYUN] CUSTOM_API_SECRET_KEY is not configured in settings')
            return None

        return GMSM4EcbCrypto(secret_key)

    def initial(self, request, *args, **kwargs):
        crypto = self.get_crypto()
        if crypto is None:
            logger.warning('[ZHUYUN] Crypto is not configured')
            super().initial(request, *args, **kwargs)
            return

        if request.method.upper() != 'POST':
            logger.warning('[ZHUYUN] Request data is not POST, raw: %s' % request.method)
            super().initial(request, *args, **kwargs)
            return

        encrypted_body = request.body
        try:
            cipher_bytes = base64.urlsafe_b64decode(encrypted_body)
            decrypted_str = crypto._decrypt(cipher_bytes)
            decrypted_data = json.loads(decrypted_str)
            request_id = decrypted_data.get('bimRequestId', 'unknown')
            logger.info(f'[ZHUYUN] Decryption success, request ID: {request_id}')
        except Exception as e:
            logger.error(f'[ZHUYUN] Decryption failed, error: {str(e)}, '
                         f'encrypted body: {encrypted_body[:100]}...')
            decrypted_data = {}

        request._full_data = decrypted_data
        super().initial(request, *args, **kwargs)

    def api_handle(self, serializer):
        return {}

    def post(self, request, *args, **kwargs):
        bid = request.data.get('bimRequestId', 'unknown')
        response_data = {'bimRequestId': bid, 'resultCode': '0', 'message': 'success'}
        logger.debug(f'[ZHUYUN] Start processing request, ID: {bid}, API: {self.__class__.__name__}')
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            api_data = self.api_handle(serializer)
            if self.override_response:
                response_data = api_data
            else:
                response_data.update(api_data)
        except Exception as e:
            error_msg = str(e)
            response_data.update({'resultCode': '500', 'message': error_msg})
            logger.error(f'[ZHUYUN] Request processing failed, ID: {bid}, error: {error_msg}')

        try:
            encode_data = json.dumps(response_data).encode('utf-8')
        except Exception as e:
            logger.error(f'[ZHUYUN] Response encryption failed, request ID: {bid}, error: {str(e)}')
            encode_data = ''

        resp_data = self.get_crypto()._encrypt(encode_data)
        return HttpResponse(
            content=base64.b64encode(resp_data).decode('utf-8'),
            status=http_status.HTTP_200_OK,
            content_type='application/octet-stream',
        )


class CustomSchemaService(BaseCustomAPIView):
    override_response = True
    serializer_class = serializers.SchemaServiceSerializer

    def api_handle(self, serializer):
        logger.debug('[ZHUYUN] Schema service data returned successfully')
        return serializer.data


class CustomCreateOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgCreateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        is_leaf = data['is_leaf']
        name = data['name']
        if not is_leaf:
            new_uid = str(uuid.uuid4())
            logger.info(f'[ZHUYUN] Non-leaf user-group return UID: {new_uid}')
            return {'uid': new_uid}

        if UserGroup.objects.filter(name=name).first():
            logger.error(f'[ZHUYUN] User group creation failed, name {name} already exists')
            raise ValueError(_('Name already exists'))
        try:
            group = UserGroup.objects.create(
                id=data['id'], name=name, comment=CREATE_BY_ZHUYUN,
            )
            logger.info(f'[ZHUYUN] User group created successfully, id: {group.id}, name: {name}')
            return {'uid': str(group.id)}
        except Exception as e:
            logger.error(f'[ZHUYUN] Org creation failed, name: {name}, error: {str(e)}')
            raise ValueError(e)


class CustomUpdateOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgUpdateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        group_id = data['bimOrgId']
        new_name = data['name']
        logger.debug(f'[ZHUYUN] Start updating user group, id: {group_id}, new name: {new_name}')

        group = UserGroup.objects.filter(id=group_id).first()
        if not group:
            logger.error(f'[ZHUYUN] User group update failed, id {group_id} does not exist')
            raise ValueError(_('%s object does not exist.') % group_id)

        group.name = new_name
        group.comment = CREATE_BY_ZHUYUN
        try:
            group.save(update_fields=['name', 'comment'])
            logger.info(f'[ZHUYUN] User group updated successfully, id: {group_id}, new name: {new_name}')
        except Exception as e:
            logger.error(f'[ZHUYUN] Org update failed, id: {group_id}, error: {str(e)}')
            raise ValueError(e)
        return {}


class CustomDeleteOrg(BaseCustomAPIView):
    serializer_class = serializers.OrgDeleteSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        group_id = data['bimOrgId']
        logger.info(f'[ZHUYUN] Start deleting user group, id: {group_id}')

        group = UserGroup.objects.filter(id=group_id).first()
        if not group:
            logger.error(f'[ZHUYUN] User group deletion failed, id {group_id} does not exist')
            raise ValueError(_('%s object does not exist.') % group_id)

        try:
            group.delete()
            logger.info(f'[ZHUYUN] User group deleted successfully, id: {group_id}, name: {group.name}')
        except Exception as e:
            logger.error(f'[ZHUYUN] User group deletion failed, id: {group_id}, error: {str(e)}')
            raise ValueError(e)
        return {}


class CustomCreateUser(BaseCustomAPIView):
    serializer_class = serializers.UserCreateSerializer

    @staticmethod
    def raise_unique_error(field_name):
        model_name = User._meta.verbose_name
        msg = _('%(model_name)s with this %(field_label)s already exists.')
        raise ValueError(msg % {'model_name': model_name, 'field_label': field_name})

    def api_handle(self, serializer):
        data = serializer.validated_data
        username, name, email = data['username'], data['name'], data['email']
        if User.objects.filter(username=username).exists():
            logger.error(f'[ZHUYUN] User creation failed, username {username} already exists')
            self.raise_unique_error(_('Username'))
        if User.objects.filter(email=email).exists():
            logger.error(f'[ZHUYUN] User creation failed, email {email} already exists')
            self.raise_unique_error(_('Email'))

        try:
            user = User.objects.create(
                id=data['id'], name=data['name'], username=data['username'],
                email=data['email'], is_active=data['is_active'],
                mfa_level=data['mfa_level'], phone=data['phone'],
                wecom_id=data['wecom_id'],
                date_expired=data['date_expired'], comment=CREATE_BY_ZHUYUN,
            )
            if group_id := data.get('group_id'):
                query = Q(id=group_id) | Q(name=data.get('group_name', 'default'))
                if g := UserGroup.objects.filter(query).first():
                    user.groups.add(g)
            logger.info(f'[ZHUYUN] User created successfully, id: {user.id}, username: {username}')
            return {'uid': str(user.id)}
        except Exception as e:
            logger.error(f'[ZHUYUN] User creation failed, username: {username}, error: {str(e)}')
            raise ValueError(e)


class CustomUpdateUser(BaseCustomAPIView):
    serializer_class = serializers.UserUpdateSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        user_id = data['bimUid']
        user = User.objects.filter(id=user_id).first()
        if not user:
            logger.error(f'[ZHUYUN] User update failed, id {user_id} does not exist')
            raise ValueError(_('%s object does not exist.') % user_id)

        update_fields = [
            'name', 'username', 'email', 'is_active', 'mfa_level',
            'phone', 'date_expired', 'wecom_id',
        ]
        try:
            save_fields = []
            for f in update_fields:
                item = data.get(f, None)
                if item is not None:
                    setattr(user, f, item)
                    save_fields.append(f)
            user.save(update_fields=save_fields)
            group_id = data.get('group_id')
            if group_id and is_uuid(group_id):
                query = Q(id=group_id) | Q(name=data.get('group_name', ''))
                user_group = UserGroup.objects.filter(query).first()
                if user_group:
                    user_group.users.add(user)
            logger.info(f'[ZHUYUN] User updated successfully, id: {user.id}, username: {user.username}')
        except Exception as e:
            logger.error(f'[ZHUYUN] User update failed, id: {user_id}, error: {str(e)}')
            raise ValueError(e)
        return {}


class CustomDeleteUser(BaseCustomAPIView):
    serializer_class = serializers.UserDeleteSerializer

    def api_handle(self, serializer):
        data = serializer.validated_data
        user_id = data['bimUid']
        user = User.objects.filter(id=user_id).first()
        if not user:
            logger.error(f'[ZHUYUN] User deletion failed, id {user_id} does not exist')
            raise ValueError(_('%s object does not exist.') % user_id)

        try:
            user.delete()
            logger.info(f'[ZHUYUN] User deleted successfully, id: {user_id}, username: {user.username}')
        except Exception as e:
            logger.error(f'[ZHUYUN] User deletion failed, id: {user_id}, error: {str(e)}')
            raise ValueError(e)
        return {}
