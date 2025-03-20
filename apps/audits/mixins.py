from django.core.cache import cache
from rest_framework.request import Request

from rbac.models import Role, RoleBinding


class SpecialAuditMixin:
    request: Request

    def _get_special_queryset(self, queryset):
        username = str(self.request.user.username)
        if username == 'auditor_admin':
            usernames = ['AuthorizedAdmin(authorized_admin)', 'SecurityAdmin(security_admin)']
            queryset = queryset.filter(user__in=usernames)
        elif username == 'authorized_admin':
            usernames = ['AuthorizedAdmin(authorized_admin)', 'SecurityAdmin(security_admin)']
            queryset = queryset.exclude(user__in=usernames)
        return queryset
