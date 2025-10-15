# -*- coding: utf-8 -*-
#
from rest_framework.generics import UpdateAPIView

from common.permissions import IsValidUser
from ..models import Asset
from ..serializers import MaintainAssetSerializer

__all__ = ['MaintainAssetApi']


class MaintainAssetApi(UpdateAPIView):
    queryset = Asset.objects.all()
    serializer_class = MaintainAssetSerializer
    permission_classes = (IsValidUser,)
    page_no_limit = True

    def check_permissions(self, request):
        obj = self.get_object()
        user = request.user
        if obj.is_offline and not user.is_superuser and f'{user.name}' != obj.maintainer:
            self.permission_denied(request)

    def perform_update(self, serializer):
        serializer.save(maintainer=self.request.user.name)
