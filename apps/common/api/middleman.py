from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import OnlySuperUser
from jumpserver.rewriting.db_backends.middleman import MiddlemanClient


class MiddlemanSQLApi(APIView):
    # TODO 后边把权限加上，严格点要求
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        return Response()


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        query_params = request.query_params.dict()
        return Response(MiddlemanClient().get_replicas(**query_params))
