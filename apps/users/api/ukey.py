import base64

from django.conf import settings
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response

from common.utils import get_logger
from common.sdk.gm import piico
from common.sdk.gm.piico.exception import PiicoError
from ..models import UKey
from ..serializers import UKeySerializer


logger = get_logger(__file__)


class UserUKeyViewSet(viewsets.ModelViewSet):
    queryset = UKey.objects.all()
    serializer_class = UKeySerializer
    search_fields = ('user__name', 'u_key_serial',)
    filterset_fields = ('user',)
    permission_classes = (AllowAny,)

    @action(detail=False, methods=['get'], url_path='random')
    def get_ukey_random(self):
        if not settings.PIICO_DEVICE_ENABLE:
            return Response({'msg': 'piico device not enable'}, status=400)

        piico_driver_path = settings.PIICO_DRIVER_PATH or './lib/libpiico_ccmu.so'
        device = piico.open_piico_device(piico_driver_path)
        try:
            random_bytes = device.generate_random(32)
            return Response({'msg': base64.b16encode(random_bytes)}, status=200)
        except PiicoError as e:
            return Response({'msg': 'random: {}'.format(e)}, status=400)
        except Exception:
            return Response({'msg': 'device not init'}, status=400)
