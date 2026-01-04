import uuid

from rest_framework import serializers

from common.serializers.fields import PhoneField
from common.utils import is_uuid, user_date_expired_default
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
            {'multivalued': False, 'name': 'email', 'required': True, 'type': 'String'},
            {'multivalued': False, 'name': 'is_active', 'required': False, 'type': 'boolean'},
            {'multivalued': False, 'name': 'mfa_level', 'required': False, 'type': 'int'},
            {'multivalued': False, 'name': 'phone', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'date_expired', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'comment', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'org_id', 'required': False, 'type': 'String'},
        ]

    @staticmethod
    def get_organization(__):
        return [
            {'multivalued': False, 'name': 'id', 'required': False, 'type': 'String'},
            {'multivalued': False, 'name': 'name', 'required': True, 'type': 'String'},
            {'multivalued': False, 'name': 'comment', 'required': False, 'type': 'String'},
        ]


class OrgCreateSerializer(BaseSerializer):
    name = serializers.CharField(required=True)
    code = serializers.CharField(required=False, allow_blank=True)
    id = serializers.UUIDField(required=False)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        _id = attrs.get('id', '')
        if not is_uuid(_id):
            if attrs.get('code'):
                real_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, attrs['code']))
            else:
                real_id = str(uuid.uuid4())
            attrs['id'] = real_id
        return attrs


class OrgUpdateSerializer(BaseSerializer):
    bimOrgId = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class OrgDeleteSerializer(BaseSerializer):
    bimOrgId = serializers.CharField(required=True)


class UserCreateSerializer(BaseSerializer):
    id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=True)
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    is_active = serializers.BooleanField(default=True, required=False)
    mfa_level = serializers.ChoiceField(choices=MFAMixin.MFA_LEVEL_CHOICES, default=0, required=False)
    phone = PhoneField(required=False)
    date_expired = serializers.DateTimeField(default=user_date_expired_default, format="%Y/%m/%d %H:%M:%S")
    comment = serializers.CharField(required=False, allow_blank=True)
    org_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        _id = attrs.get('id', '')
        if not is_uuid(_id):
            attrs['id'] = str(uuid.uuid4())
        return attrs


class UserUpdateSerializer(BaseSerializer):
    bimUid = serializers.UUIDField(required=True)
    name = serializers.CharField(required=True)
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    is_active = serializers.EmailField(default=True, required=False)
    mfa_level = serializers.ChoiceField(choices=MFAMixin.MFA_LEVEL_CHOICES, default=0, required=False)
    phone = PhoneField(required=False)
    date_expired = serializers.DateTimeField(default=user_date_expired_default, format="%Y/%m/%d %H:%M:%S")
    comment = serializers.CharField(required=False, allow_blank=True)
    org_id = serializers.UUIDField(required=False)


class UserDeleteSerializer(BaseSerializer):
    bimUid = serializers.CharField(required=True)
