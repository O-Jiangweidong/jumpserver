from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from common.permissions import OnlySuperUser
from common.utils import middleman_client


class MiddlemanApi(APIView):
    permission_classes = (OnlySuperUser,)

    @staticmethod
    def get(request, *args, **kwargs):
        query_data = request.query_params.dict()
        action_ = query_data.pop('action', '')
        if action_ == 'get_slave_index':
            res = middleman_client.get_slaves(filter='index')
        elif action_ == 'get_slave_nodes':
            res = middleman_client.get_slaves()
        elif action_ == 'get_tasks':
            res = middleman_client.get_tasks(**query_data)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(res)
