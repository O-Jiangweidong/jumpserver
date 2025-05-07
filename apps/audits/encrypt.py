import binascii
import os

from ctypes import *

from common.utils import get_logger
from jumpserver.const import PROJECT_DIR


logger = get_logger(__name__)


class AuditCryptoHandler(object):
    SECRET_KEY = bytearray.fromhex(
        '6c f0 20 0b c8 1a 83 01 25 60 1f c8 a4 bd 14 15 dd ca 64 4a 73 75 2d 1a 10 85 48 28 19 fc 82 11'
    )

    def __init__(self):
        so_path = os.path.join(PROJECT_DIR, 'PCI-E/lib/libsdf.so')
        self._sdf_lib = cdll.LoadLibrary(so_path)
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
            b_c_text = binascii.hexlify(bytes(return_value))  # b2a_hex
            encrypt_data = str(b_c_text, encoding="utf-8").upper()
            logger.debug('AuditCryptoHandler SDFE_Hmac ret code: %s, result: %s' % (ret, encrypt_data))
        except Exception as e:
            logger.error('AuditCryptoHandler encrypt failed: %s' % e)
        return encrypt_data

    def fill_data(self, data):
        encrypt_fields = ','.join(data.keys())
        encrypt_value = self.encrypt(''.join(map(lambda x: str(x), data.values())))
        data.update({
            'encrypt_fields': encrypt_fields, 'encrypt_value': encrypt_value
        })
        return data


audit_crypto_handler = AuditCryptoHandler()
