import uuid

from django.conf import settings
from rest_framework import serializers

from common.serializers.fields import PhoneField
from common.utils import user_date_expired_default
from users.models import MFAMixin


class BaseSerializer(serializers.Serializer):
    bimRequestId = serializers.CharField(required=True)


class SchemaServiceSerializer(BaseSerializer):
    account = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    @staticmethod
    def get_account(__):
        return [
            {'multivalued': False, 'name': 'id', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'username', 'required': True, 'type': 'String'},
            {'multivalued': False, 'name': 'name', 'required': True, 'type': 'String'},
            {'multivalued': False, 'name': 'email', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'is_active', 'required': False, 'type': 'boolean'},
            {'multivalued': False, 'name': 'mfa_level', 'required': False, 'type': 'int'},
            {'multivalued': False, 'name': 'phone', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'date_expired', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'group_id', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'group_name', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'wecom_id', 'required': False, 'type': 'String'},
        ]

    @staticmethod
    def get_organization(__):
        return [
            {'multivalued': False, 'name': 'id', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'name', 'required': True, 'type': 'String'},
            {'multivalued': False, 'name': 'is_leaf', 'required': True, 'type': 'boolean'},
        ]


class OrgCreateSerializer(BaseSerializer):
    id = serializers.CharField(required=False)
    name = serializers.CharField(required=True)
    is_leaf = serializers.BooleanField(required=True)

    @staticmethod
    def validate_name(name):
        return name.rsplit('/', 1)[-1]

    def validate(self, attrs):
        _id = attrs.get('id', '')
        if _id:
            real_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, _id))
        else:
            real_id = str(uuid.uuid4())
        attrs['id'] = real_id
        return attrs


class OrgUpdateSerializer(BaseSerializer):
    bimOrgId = serializers.CharField(required=True)
    name = serializers.CharField(required=True)

    @staticmethod
    def validate_name(name):
        return name.rsplit('/', 1)[-1]


class OrgDeleteSerializer(BaseSerializer):
    bimOrgId = serializers.CharField(required=True)


class UserBaseSerializer(BaseSerializer):
    name = serializers.CharField(required=True)
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, default='')
    wecom_id = serializers.CharField(required=False, default='')
    is_active = serializers.BooleanField(default=True, required=False)
    mfa_level = serializers.ChoiceField(choices=MFAMixin.MFA_LEVEL_CHOICES, default=0, required=False)
    phone = PhoneField(required=False)
    date_expired = serializers.DateTimeField(default=user_date_expired_default, format="%Y/%m/%d %H:%M:%S")
    group_id = serializers.UUIDField(required=False)
    group_name = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get('email', ''):
            suffix = settings.EMAIL_SUFFIX or 'example.com'
            attrs['email'] = f'{attrs["username"]}@{suffix}'
        return attrs


class UserCreateSerializer(UserBaseSerializer):
    id = serializers.UUIDField(required=False, default=uuid.uuid4)


class UserUpdateSerializer(UserBaseSerializer):
    bimUid = serializers.UUIDField(required=True)


class UserDeleteSerializer(BaseSerializer):
    bimUid = serializers.UUIDField(required=True)
