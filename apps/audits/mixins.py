from django.core.cache import cache
from rest_framework.request import Request

from rbac.models import Role, RoleBinding


authorized_admin = 'AuthorizedAdmin(authorized_admin)'
security_admin = 'SecurityAdmin(security_admin)'
auditor_admin = 'AuditorAdmin(auditor_admin)'


class SpecialOperateLogMixin:
    request: Request

    def _get_special_queryset(self, queryset):
        username = str(self.request.user.username)
        usernames = [authorized_admin, security_admin]
        if username == 'auditor_admin':
            queryset = queryset.filter(user__in=usernames)
        elif username == 'authorized_admin':
            queryset = queryset.exclude(user__in=usernames)
        return queryset


class SpecialLoginLogMixin:
    request: Request

    def _get_special_queryset(self, queryset):
        username = str(self.request.user.username)
        usernames = [auditor_admin, security_admin, 'auditor_admin', 'security_admin']
        if username == 'auditor_admin':
            queryset = queryset.filter(username__in=usernames)
        elif username == 'authorized_admin':
            queryset = queryset.exclude(username__in=usernames)
        return queryset
