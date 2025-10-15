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
