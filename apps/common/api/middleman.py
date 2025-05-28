from rest_framework.views import APIView
from rest_framework.response import Response

from common.permissions import OnlySuperUser
from common.utils import middleman_client


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        slave_name = request.headers.get('x-slave-name', '')
        query_data = request.query_params.dict()
        action_ = query_data.pop('action', '')
        handler = getattr(middleman_client, action_, lambda *k, **kw: {})
        return Response(handler(slave_name=slave_name, **query_data))
