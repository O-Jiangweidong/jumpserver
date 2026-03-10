import requests

from celery import shared_task

from common.utils import get_logger



logger = get_logger(__name__)


@shared_task(verbose_name='Send command review ticket message')
def send_message_to_external(url, data):
    try:
        resp = requests.post(url, json=data)
        resp.raise_for_status()
    except Exception as error:
        logger.error(f'Error sending command review ticket message: {error}')
