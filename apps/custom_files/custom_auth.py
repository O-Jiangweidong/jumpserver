import os
import hashlib

import requests

from django.conf import settings
from common.utils import get_logger


logger = get_logger(__name__)


def get_md5(raw):
    return hashlib.md5(raw.encode()).hexdigest()


def authenticate(username, password, **kwargs):
    access_key = os.environ.get('CUSTOM_AUTH_ACCESS_KEY')
    secret_key = os.environ.get('CUSTOM_AUTH_SECRET_KEY')
    sign = os.environ.get('CUSTOM_AUTH_SIGN')
    url = os.environ.get('CUSTOM_AUTH_URL')

    headers = {
        'otp-sign': sign, 'otp-ak': access_key, 'opt-sk': secret_key
    }
    data = {'token': password, 'account': username}
    try:
        resp = requests.post(url, json=data, headers=headers)
        resp.raise_for_status()
        status = resp.json().get('data', {}).get('status', False)
        if status is False:
            logger.warning("PinAuthBackend failed, status error")
            return None
    except Exception as e:
        logger.warning("PinAuthBackend failed, except happened:%s" % e)
        return None
    return {
        'name': username, 'username': username, 'is_active': True
    }
