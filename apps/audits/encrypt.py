import binascii
import hmac
import hashlib
import os

from ctypes import *

from django.conf import settings

from common.utils import get_logger, is_true


logger = get_logger(__name__)


class HmacEncryptor:
    def __init__(self, secret_key):
        self.secret_key = secret_key

    def encrypt(self, data, default=''):
        hmac_obj = hmac.new(self.secret_key, msg=data, digestmod=hashlib.sha256)
        return hmac_obj.hexdigest().upper()


class PIICOHmacEncryptor(HmacEncryptor):
    def __init__(self, secret_key):
        super().__init__(secret_key)

        driver_path = settings.PIICO_DRIVER_PATH if settings.PIICO_DRIVER_PATH\
            else "./lib/libpiico_ccmu.so"
        self._sdf_lib = cdll.LoadLibrary(driver_path)
        self._session, self._device = None, None
        self._init()

    def _init(self):
        self._open_device()
        self._open_session()

    def _open_device(self):
        # 定义参数类型
        SDFE_OpenDevice = self._sdf_lib.SDFE_OpenDevice
        device_handle = c_void_p()
        # 调用函数
        ret = SDFE_OpenDevice(pointer(device_handle), 0)
        logger.debug('AuditCryptoHandler SDFE_OpenDevice ret: %s' % ret)
        self._device = device_handle
        return ret

    def _open_session(self):
        # 定义参数类型
        SDFE_OpenSession = self._sdf_lib.SDFE_OpenSession
        # 调用函数
        session_handle = c_void_p()
        ret = SDFE_OpenSession(self._device, pointer(session_handle))
        logger.debug('AuditCryptoHandler SDFE_OpenSession ret: %s' % ret)
        self._session = session_handle
        return ret

    def encrypt(self, data, default=''):
        encrypt_data = default
        try:
            _key = (c_ubyte * 32)(*self.SECRET_KEY)
            data = bytes(data, encoding='utf-8')
            hash_len = c_uint32(0)
            ui_key_len = len(_key)  # c_int(len(key))

            return_value = (c_uint8 * 32)()
            ret = self._sdf_lib.SDFE_Hmac(
                self._session, _key, ui_key_len, data, len(data),
                return_value, pointer(hash_len)
            )
            logger.debug('AuditCryptoHandler SDFE_Hmac %s' % ret)
            array = bytes(return_value)
            b_c_text = binascii.hexlify(array)  # b2a_hex
            encrypt_data = str(b_c_text, encoding="utf-8").upper()
        except Exception as e:
            logger.error('Audit Models Exception: %s' % e)
        return encrypt_data


class AuditCryptoHandler(object):
    SECRET_KEY = bytearray.fromhex(
        '6c f0 20 0b c8 1a 83 01 25 60 1f c8 a4 bd 14 15 dd ca 64 4a 73 75 2d 1a 10 85 48 28 19 fc 82 11'
    )

    def __init__(self):
        self._encryptor = self._get_encryptor()

    def _get_encryptor(self):
        use_piico_hmac = is_true(os.environ.get('USE_PIICO_HMAC', '0'))
        if settings.GMSSL_ENABLED and settings.PIICO_DEVICE_ENABLE and use_piico_hmac:
            return PIICOHmacEncryptor(self.SECRET_KEY)
        return HmacEncryptor(self.SECRET_KEY)

    def encrypt(self, data, default=''):
        return self._encryptor.encrypt(data, default)

    def fill_data(self, data):
        if not settings.ENABLE_LOG_MAC_CALCULATION:
            return data

        encrypt_fields = ','.join(data.keys())
        encrypt_value = self.encrypt(''.join(map(lambda x: str(x), data.values())))
        data.update({
            'encrypt_fields': encrypt_fields, 'encrypt_value': encrypt_value
        })
        return data


audit_crypto_handler = AuditCryptoHandler()
