import os
import hashlib

import requests

from django.conf import settings


def get_md5(raw):
    return hashlib.md5(raw.encode()).hexdigest()


def authenticate(username, password, **kwargs):
    access_key = os.environ.get('CUSTOM_AUTH_ACCESS_KEY')
    secret_key = os.environ.get('CUSTOM_AUTH_SECRET_KEY')
    url = os.environ.get('CUSTOM_AUTH_URL')

    headers = {
        'otp-sign': get_md5(f'{access_key}{secret_key}'),
        'otp-ak': access_key
    }
    data = {'token': password, 'ucid': username}
    requests.post(url, json=data, headers=headers).raise_for_status()
    email_suffix = settings.EMAIL_SUFFIX or 'jumpserver.com'
    return {
        'name': username,
        'username': username,
        'email': f'{username}@{email_suffix}',
        'is_active': True
    }
