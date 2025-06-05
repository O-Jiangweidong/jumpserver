from rest_framework.validators import UniqueValidator

from common.serializers.fields import ObjectRelatedField, ObjectManyRelatedField
from common.validators import ProjectUniqueValidator


class MiddlemanSerializerMixin(object):
    @staticmethod
    def _clean_serializer_fields(serializer):
        s_validators = []
        for v in serializer.validators:
            if isinstance(v, ProjectUniqueValidator):
                continue
            s_validators.append(v)
        serializer.validators = s_validators

        for __, field in serializer.fields.items():
            if isinstance(field, (ObjectRelatedField, ObjectManyRelatedField)):
                setattr(field, 'ignore_to_internal_value', True)

            validators = []
            for v in field.validators:
                if isinstance(v, UniqueValidator):
                    continue
                validators.append(v)
            field.validators = validators
        return serializer
