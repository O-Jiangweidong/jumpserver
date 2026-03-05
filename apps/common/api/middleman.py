from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class MiddlemanSQLApi(APIView):
    # TODO 后边把权限加上，严格点要求
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        return Response()
