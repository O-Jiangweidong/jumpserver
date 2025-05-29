from rest_framework.views import APIView
from rest_framework.response import Response

from common.permissions import OnlySuperUser
from common.utils import middleman_client


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        return Response(middleman_client.get_slave_nodes())
