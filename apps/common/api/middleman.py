import django.db.utils
from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import OnlySuperUser, IsServiceAccount
from common.utils import get_logger
from jumpserver.rewriting.db_backends.middleman import MiddlemanClient


logger = get_logger(__name__)


class MiddlemanSQLApi(APIView):
    permission_classes = (IsServiceAccount,)

    def post(self, request, *args, **kwargs):
        sql = request.data.get('sql', '')
        params = request.data.get('params', [])
        if not sql or not isinstance(params, list):
            return Response({'error': 'sql or param is invalid'}, status=400)

        with connection.cursor() as cursor:
            logger.debug('Middleman SQL: {}'.format(cursor.mogrify(sql, params)))
            try:
                cursor.execute(sql, params)
            except django.db.utils.IntegrityError as e:
                if "for key 'django_content_type.django_content_type" not in str(e):
                    raise e
        return Response()


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        query_params = request.query_params.dict()
        return Response(MiddlemanClient().get_replicas(**query_params))
