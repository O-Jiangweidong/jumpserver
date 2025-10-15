# -*- coding: utf-8 -*-
#

from rest_framework import serializers

from ..models import Asset

__all__ = ['MaintainAssetSerializer']


class MaintainAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['is_offline', 'maintainer']
        read_only_fields = ['maintainer']
