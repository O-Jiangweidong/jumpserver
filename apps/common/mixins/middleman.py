from django.conf import settings
from django.http import Http404
from rest_framework.validators import UniqueValidator
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from common.exceptions import JMSException
from common.serializers.fields import (
    ObjectRelatedField, ObjectManyRelatedField, ObjectPrimaryKeyRelatedField
)
from common.validators import ProjectUniqueValidator
from common.utils import lazyproperty, middleman_client


class MiddlemanMixin(object):
    request: Request
    tp: str = ''
    use_middleman_retrieve: bool = True
    use_middleman_update: bool = True
    use_middleman_create: bool = True
    use_middleman_destroy: bool = True

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
        if not hasattr(serializer, 'fields'):
            return serializer

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
        if self.has_middleman_master_behavior() and self.use_middleman_retrieve:
            return None
        return super().get_object()

    @staticmethod
    def _get_id(**kwargs):
        id_ = kwargs.get('pk', '')
        if not id_:
            raise Http404()
        return id_

    @staticmethod
    def clean_retrieve_result(result):
        return result

    def retrieve(self, request, *args, **kwargs):
        if self.has_middleman_master_behavior() and self.use_middleman_retrieve:
            id_ = self._get_id(**kwargs)
            resp = middleman_client.get_detail(
                type_=self.tp, id_=id_, slave_name=self.slave_name
            )
            data = self.raise_failed_request(resp)
            data = self.clean_retrieve_result(data)
            return Response(data)
        else:
            return super().retrieve(request, *args, **kwargs)

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        if self.has_middleman_master_behavior():
            serializer = self._clean_serializer_fields(serializer)
        return serializer

    def _build_data(self, *args, **kwargs):
        raise JMSException('Unsupported API request')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not self.tp or not self.use_middleman_create:
            return super().perform_create(serializer)

        if self.has_middleman_master_behavior():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_=self.tp, data=[data], slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            serializer.validated_data['id'] = data['id']
            return_data = serializer.validated_data
        elif self.is_middleman_slave() and not self.from_middleman():
            data = self._build_data(self.request, serializer)
            resp = middleman_client.post_resource(
                type_=self.tp, data=[data], slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            serializer.validated_data['id'] = data['id']
            super().perform_create(serializer)
            return_data = serializer.data
        else:
            super().perform_create(serializer)
            return_data = serializer.data
        return Response(return_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        if not self.tp or not self.use_middleman_update:
            return super().update(request, *args, **kwargs)

        partial = kwargs.get('partial', False) and self.tp == 'node'
        if self.has_middleman_master_behavior():
            id_ = self._get_id(**kwargs)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = self._build_data(request, serializer, id_, is_create=False)
            resp = middleman_client.update_resource(
                type_=self.tp, id_=id_, data=data, partial=partial, slave_name=self.slave_name
            )
            data = self.raise_failed_request(resp)
            return Response(status=resp.status_code, data=data)
        elif self.is_middleman_slave() and not self.from_middleman():
            id_ = self._get_id(**kwargs)
            serializer = self.get_serializer(instance=self.get_object(), data=request.data)
            serializer.is_valid(raise_exception=True)
            data = self._build_data(request, serializer, id_, is_create=False)
            resp = middleman_client.update_resource(
                type_=self.tp, id_=id_, data=data, partial=partial, slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            return super().update(request, *args, **kwargs)
        else:
            return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.tp or not self.use_middleman_destroy:
            return super().destroy(request, *args, **kwargs)

        if self.has_middleman_master_behavior():
            id_ = self._get_id(**kwargs)
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            return Response(status=resp.status_code, data=resp.json())
        elif self.is_middleman_slave() and not self.from_middleman():
            id_ = self._get_id(**kwargs)
            resp = middleman_client.delete_instance(
                tp=self.tp, id_=id_, slave_name=self.slave_name
            )
            self.raise_failed_request(resp)
            return super().destroy(request, *args, **kwargs)
        else:
            return super().destroy(request, *args, **kwargs)
