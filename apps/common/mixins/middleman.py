from rest_framework.validators import UniqueValidator

from common.serializers.fields import ObjectRelatedField, ObjectManyRelatedField


class MiddlemanSerializerMixin(object):
    @staticmethod
    def _clean_serializer_fields(serializer):
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
