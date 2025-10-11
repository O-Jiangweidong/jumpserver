from ctypes import *

from .cipher import *
from .digest import *
from .exception import PiicoError
from .session import Session
from common.utils import get_logger


logger = get_logger(__file__)


class Device:
    _driver = None
    __device = None

    def open(self, driver_path="./libpiico_ccmu.so"):
        # load driver
        self.__load_driver(driver_path)
        # open device
        self.__open_device()

    def close(self):
        if self.__device is None:
            raise PiicoError("device not turned on", -1)
        ret = self._driver.SDF_CloseDevice(self.__device)
        if ret != 0:
            raise PiicoError("turn off device failed", -1)
        self.__device = None

    def new_session(self):
        session = c_void_p()
        ret = self._driver.SDF_OpenSession(self.__device, pointer(session))
        if ret != 0:
            raise PiicoError("create session failed")
        return Session(self._driver, session)

    def generate_ecc_key_pair(self):
        session = self.new_session()
        return session.generate_ecc_key_pair(alg_id=0x00020200)

    def verify_sign(self, public_key, raw_data, sign_data):
        logger.debug("verify_sign public_key: %s", public_key)
        logger.debug("verify_sign raw_data: %s", raw_data)
        logger.debug("verify_sign sign_data: %s", sign_data)
        session = self.new_session()
        return session.verify_sign_ecc(0x00020200, public_key, raw_data, sign_data)

    def generate_random(self, length=64):
        session = self.new_session()
        return session.generate_random(length)

    def new_sm2_ecc_cipher(self, public_key, private_key):
        session = self.new_session()
        return ECCCipher(session, public_key, private_key)

    def new_sm4_ebc_cipher(self, key_val):
        session = self.new_session()
        return EBCCipher(session, key_val)

    def new_sm4_cbc_cipher(self, key_val, iv):
        session = self.new_session()
        return CBCCipher(session, key_val, iv)

    def new_digest(self, mode="sm3"):
        session = self.new_session()
        return Digest(session, mode)

    def __load_driver(self, path):
        # check driver status
        if self._driver is not None:
            raise PiicoError("already load driver", -1)
        # load driver
        self._driver = cdll.LoadLibrary(path)

    def __open_device(self):
        device = c_void_p()
        ret = self._driver.SDF_OpenDevice(pointer(device))
        if ret != 0:
            raise PiicoError("open piico device failed", ret)
        self.__device = device
