from django.conf import settings
from django.http import Http404
from rest_framework.validators import UniqueValidator
from rest_framework.request import Request
from rest_framework.response import Response

from common.serializers.fields import (
    ObjectRelatedField, ObjectManyRelatedField, ObjectPrimaryKeyRelatedField
)
from common.validators import ProjectUniqueValidator
from common.utils import lazyproperty, middleman_client


class MiddlemanMixin(object):
    request: Request
    tp: str

    @lazyproperty
    def slave_name(self):
        slave_name, h_salve_name = settings.MIDDLEMAN_SERVICE_NAME, None
        if self.is_middleman_master():
            h_salve_name = self.request.headers.get('x-slave-name')
        return h_salve_name or slave_name

    @staticmethod
    def is_middleman_master():
        return settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower() == 'master'

    def has_middleman_master_behavior(self):
        h_salve_name = self.request.headers.get('x-slave-name')
        return h_salve_name and settings.MIDDLEMAN_SERVICE_NAME != h_salve_name

    @staticmethod
    def is_middleman_slave():
        return settings.MIDDLEMAN_SERVICE_ROLE_NAME.lower() == 'slave'

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

    def destroy(self, request, *args, **kwargs):
        if not self.tp:
            raise Http404()

        id_ = kwargs.get('pk', '')
        if self.has_middleman_master_behavior():
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            return Response(status=resp.status_code, data=resp.json())
        elif self.is_middleman_slave():
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            resp.raise_for_status()
            return super().destroy(request, *args, **kwargs)
        else:
            return super().destroy(request, *args, **kwargs)
