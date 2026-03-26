from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jumpserver.rewriting.db_backends.middleman import MiddlemanClient


# TODO 下边三个试图一定要把权限做好，执行sql的权限一定要慎重，防止sql注入风险
class MiddlemanSQLApi(APIView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        return Response()


class MiddlemanReplicaApi(APIView):
    permission_classes = (AllowAny,)

    @staticmethod
    def get(request, *args, **kwargs):
        query_params = request.query_params.dict()
        return Response(MiddlemanClient().get_replicas(**query_params))


class MiddlemanTaskApi(APIView):
    permission_classes = (AllowAny,)

    @staticmethod
    def get(request, *args, **kwargs):
        query_params = request.query_params.dict()
        return Response(MiddlemanClient().get_tasks(**query_params))
