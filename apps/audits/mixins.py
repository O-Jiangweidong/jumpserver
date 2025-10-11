from django.db import models
from django.utils.translation import gettext_lazy as _

from audits.encrypt import audit_crypto_handler


class AuditEncryptModel(object):
    encrypt_fields: str = models.CharField(max_length=1024, default='', verbose_name=_('Encrypt fields'))
    encrypt_value = models.CharField(max_length=1024, default='', verbose_name=_('Encrypt value'))

    class Meta:
        abstract = True

    @property
    def hmac_verify(self):
        raw_value = ''
        for f in self.encrypt_fields.split(','):
            raw_value += str(getattr(self, f, ''))
        return self.encrypt_value == audit_crypto_handler.encrypt(raw_value, default='0')
