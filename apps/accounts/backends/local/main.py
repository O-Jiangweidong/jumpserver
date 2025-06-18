from azure.identity import ClientSecretCredential
from django.conf import settings

from common.utils import get_logger
from ..base import BaseVault

logger = get_logger(__name__)

__all__ = ['Vault']


class Vault(BaseVault):

    def is_active(self):
        return True, ''

    @staticmethod
    def _get_secret_from_aad_sp(auth_url, resource_url):
        try:
            credential = ClientSecretCredential(
                tenant_id=settings.AAD_TENANT_ID,
                client_id=settings.AAD_CLIENT_ID,
                client_secret=settings.AAD_CLIENT_SECRET,
                authority=auth_url
            )

            token = credential.get_token(f"{resource_url}/.default")
            return token.token
        except Exception as e: # noqa
            return None

    def _get(self, instance):
        primary_protocol = instance.platform.protocols.filter(primary=True).first()
        if primary_protocol and primary_protocol.name in ('postgresql', 'mysql'):
            setting = primary_protocol.setting
            if setting.get('auth_method') == 'azure-aad':
                auth_url = setting.get('authority_url')
                resource_url = setting.get('resource_url')
                secret = self._get_secret_from_aad_sp(auth_url, resource_url)
                setattr(instance, '_secret', secret)
        secret = getattr(instance, '_secret', None)
        return secret

    def _create(self, instance):
        """ Ignore """
        pass

    def _update(self, instance):
        """ Ignore """
        pass

    def _delete(self, instance):
        """ Ignore """
        pass

    def _save_metadata(self, instance, metadata):
        """ Ignore """
        pass

    def _clean_db_secret(self, instance):
        """ Ignore *重要* 不能删除本地 secret """
        pass
