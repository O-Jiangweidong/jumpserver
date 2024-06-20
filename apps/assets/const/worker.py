from django.utils.translation import gettext_lazy as _

from .base import BaseType


WORKER_NAME = 'Worker'


class WorkerTypes(BaseType):
    WORKER = 'worker', _('Worker')

    @classmethod
    def _get_base_constrains(cls) -> dict:
        return {
            '*': {
                'charset_enabled': False,
                'domain_enabled': False,
                'su_enabled': False,
            }
        }

    @classmethod
    def _get_automation_constrains(cls) -> dict:
        constrains = {
            '*': {
                'ansible_enabled': False,
                'ping_enabled': False,
                'gather_facts_enabled': False,
                'verify_account_enabled': False,
                'change_secret_enabled': False,
                'push_account_enabled': False,
                'gather_accounts_enabled': False,
            }
        }
        return constrains

    @classmethod
    def _get_protocol_constrains(cls) -> dict:
        return {
            '*': {
                'choices': ['ssh'],
            }
        }

    @classmethod
    def internal_platforms(cls):
        return {
            cls.WORKER: [
                {'name': WORKER_NAME},
            ],
        }

    @classmethod
    def get_community_types(cls):
        return [
            cls.WORKER,
        ]
