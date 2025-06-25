from django.conf import settings
from django.http import Http404
from rest_framework.validators import UniqueValidator
from rest_framework.request import Request
from rest_framework.response import Response

from common.exceptions import JMSException
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

    def from_middleman(self):
        return self.request.headers.get('x-middleman-version', '')

    @staticmethod
    def raise_failed_request(response):
        try:
            data = response.json()
        except Exception: # noqa
            data = {}

        if response.status_code >= 300:
            raise JMSException(data)
        return data

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

    def get_object(self):
        if self.has_middleman_master_behavior():
            return None
        return super().get_object()

    def destroy(self, request, *args, **kwargs):
        id_ = kwargs.get('pk', '')
        if not self.tp or not id_:
            raise Http404()

        destroy_func = super().destroy
        if hasattr(self, 'raw_destroy'):
            destroy_func = self.raw_destroy
        if self.has_middleman_master_behavior():
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            return Response(status=resp.status_code, data=resp.json())
        elif self.is_middleman_slave() and not self.from_middleman():
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            return destroy_func(request, *args, **kwargs)
        else:
            return destroy_func(request, *args, **kwargs)
