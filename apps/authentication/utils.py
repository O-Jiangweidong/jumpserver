# -*- coding: utf-8 -*-
#
import ctypes

import ipaddress
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from audits.const import DEFAULT_CITY
from users.models import User
from common.utils import get_logger, get_object_or_none
from common.utils import validate_ip, get_ip_city, get_request_ip
from .notifications import DifferentCityLoginMessage

logger = get_logger(__file__)


def check_different_city_login_if_need(user, request):
    from audits.models import UserLoginLog

    if not settings.SECURITY_CHECK_DIFFERENT_CITY_LOGIN:
        return

    ip = get_request_ip(request) or '0.0.0.0'
    city_white = [_('LAN'), 'LAN']
    is_private = ipaddress.ip_address(ip).is_private
    if is_private:
        return
    usernames = [user.username, f"{user.name}({user.username})"]
    last_user_login = UserLoginLog.objects.exclude(
        city__in=city_white
    ).filter(username__in=usernames, status=True).first()
    if not last_user_login:
        return

    city = get_ip_city(ip)
    last_city = get_ip_city(last_user_login.ip)
    if city == last_city:
        return

    DifferentCityLoginMessage(user, ip, city).publish_async()


def build_absolute_uri(request, path=None):
    """ Build absolute redirect """
    if path is None:
        path = '/'
    site_url = urlparse(settings.SITE_URL)
    scheme = site_url.scheme or request.scheme
    host = request.get_host()
    url = f'{scheme}://{host}'
    redirect_uri = urljoin(url, path)
    return redirect_uri


def build_absolute_uri_for_oidc(request, path=None):
    """ Build absolute redirect uri for OIDC """
    if path is None:
        path = '/'
    if settings.BASE_SITE_URL:
        # OIDC 专用配置项
        redirect_uri = urljoin(settings.BASE_SITE_URL, path)
        return redirect_uri
    return build_absolute_uri(request, path=path)


def check_user_property_is_correct(username, **properties):
    user = get_object_or_none(User, username=username)
    for attr, value in properties.items():
        if getattr(user, attr, None) != value:
            user = None
            break
    return user


UByte64Array = ctypes.c_ubyte * 64


class ECCrefPublicKey(ctypes.Structure):
    _fields_ = [
        ('bits', ctypes.c_uint), ('x', UByte64Array), ('y', UByte64Array),
    ]


class ECCSignature(ctypes.Structure):
    _fields_ = [("r", UByte64Array), ("s", UByte64Array)]


class ECCCryptoHandler(object):
    def __init__(self):
        self._sdf_lib = ctypes.cdll.LoadLibrary("/opt/jumpserver/PCI-E/lib/libsdf.so")
        self._session, self._device = None, None

    def _pre_check(self):
        device_ret = self._open_device()
        session_ret = self._open_session()
        return device_ret or session_ret

    def generate_random(self, length):
        # 定义参数类型
        SDF_GenerateRandom = self._sdf_lib.SDF_GenerateRandom
        SDF_GenerateRandom.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte)]
        SDF_GenerateRandom.restype = ctypes.c_int
        # 调用函数
        random_data = (ctypes.c_ubyte * length)()
        SDF_GenerateRandom(self._session, length, random_data)
        return bytes(random_data)

    def _open_device(self):
        # 定义参数类型
        SDF_OpenDevice = self._sdf_lib.SDF_OpenDevice
        SDF_OpenDevice.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        device_handle = ctypes.c_void_p()
        # 调用函数
        ret = SDF_OpenDevice(ctypes.byref(device_handle))
        self._device = device_handle
        return ret

    def _open_session(self):
        # 定义参数类型
        SDF_OpenSession = self._sdf_lib.SDF_OpenSession
        SDF_OpenSession.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        SDF_OpenSession.restype = ctypes.c_int
        # 调用函数
        session_handle = ctypes.c_void_p()
        ret = SDF_OpenSession(self._device, ctypes.byref(session_handle))
        self._session = session_handle
        return ret

    def verify_ecc(self, public_key_data, raw_data, sign_r, sign_s):
        info_msg = (f'Public key x+y: {public_key_data}'
                    f'Token AB: {raw_data}, R: {sign_r}, S: {sign_s}')
        logger.debug(info_msg)
        ret = self._pre_check()
        if ret:
            logger.error('Pre check error: %s' % ret)
            return

        try:
            public_key_data = bytes.fromhex(public_key_data)
            plain_text = (ctypes.c_ubyte * len(raw_data))(*raw_data)

            # 创建ECCrefPublicKey和ECCSignature结构体实例
            k1 = bytes([0] * 32) + public_key_data[0:32]
            k2 = bytes([0] * 32) + public_key_data[32:64]
            pk = ECCrefPublicKey(ctypes.c_uint(0x100), (UByte64Array)(*k1), (UByte64Array)(*k2))

            r = bytes([0] * 32) + sign_r
            s = bytes([0] * 32) + sign_s
            signature = ECCSignature((UByte64Array)(*r), (UByte64Array)(*s))

            # 调用函数
            ret = self._sdf_lib.SDF_ExternalVerify_ECC(
                self._session, ctypes.c_uint(0x00020100), ctypes.pointer(pk), plain_text,
                ctypes.c_uint(len(plain_text)), ctypes.pointer(signature)
            )
            logger.debug('SDF_ExternalVerify_ECC code: %s' % ret)
        except Exception as err:
            logger.error('SDF_ExternalVerify_ECC Failed: %s' % err)
            ret = 1
        return ret == 0

    def _close_session(self):
        # 定义参数类型
        SDF_CloseSession = self._sdf_lib.SDF_CloseSession
        SDF_CloseSession.argtypes = [ctypes.c_void_p]
        SDF_CloseSession.restype = ctypes.c_int
        # 调用函数
        ret = SDF_CloseSession(self._session)
        return ret

    def _close_device(self):
        # 定义参数类型
        SDF_CloseDevice = self._sdf_lib.SDF_CloseDevice
        SDF_CloseDevice.argtypes = [ctypes.c_void_p]
        SDF_CloseDevice.restype = ctypes.c_int
        # 调用函数
        ret = SDF_CloseDevice(self._device)
        return ret

    def __del__(self):
        if self._session:
            self._close_session()
        if self._device:
            self._close_device()
