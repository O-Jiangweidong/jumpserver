from django.conf import settings
from rest_framework.validators import UniqueValidator
from rest_framework.request import Request

from common.serializers.fields import (
    ObjectRelatedField, ObjectManyRelatedField, ObjectPrimaryKeyRelatedField
)
from common.validators import ProjectUniqueValidator
from common.utils import lazyproperty


class MiddlemanSerializerMixin(object):
    request: Request

    @lazyproperty
    def slave_name(self):
        return self.request.headers.get('x-slave-name')

    def is_middleman_master(self):
        # TODO middleman: 后边把这个解开
        is_master = True
        # is_master = settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower() == 'master'
        return self.slave_name and is_master

    @staticmethod
    def _clean_serializer_fields(serializer):
        s_validators = []
        for v in serializer.validators:
            if isinstance(v, ProjectUniqueValidator):
                continue
            s_validators.append(v)
        serializer.validators = s_validators

        for __, field in serializer.fields.items():
            if isinstance(field, (
                    ObjectRelatedField, ObjectManyRelatedField, ObjectPrimaryKeyRelatedField
            )):
                setattr(field, 'ignore_to_internal_value', True)

            validators = []
            for v in field.validators:
                if isinstance(v, UniqueValidator):
                    continue
                validators.append(v)
            field.validators = validators
        return serializer
