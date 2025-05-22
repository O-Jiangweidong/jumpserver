from rest_framework.views import APIView
from rest_framework.response import Response

from common.permissions import OnlySuperUser
from common.utils import middleman_client


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        post_data = request.query_params.dict()
        action = post_data.pop('action')
        handler = getattr(middleman_client, action, lambda *k, **kw: {})
        return Response(handler(**post_data))
