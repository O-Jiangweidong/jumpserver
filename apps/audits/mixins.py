from rest_framework.request import Request


class SpecialOperateLogMixin:
    request: Request

    def _get_special_queryset(self, queryset):
        username = str(self.request.user.username)
        usernames = ['安全保密管理员(secadmin)', '系统管理员(sysadmin)']
        if username == 'auadmin':
            queryset = queryset.filter(user__in=usernames)
        elif username == 'secadmin':
            queryset = queryset.exclude(user__in=usernames)
        return queryset


class SpecialLoginLogMixin:
    request: Request

    def _get_special_queryset(self, queryset):
        username = str(self.request.user.username)
        usernames = [
            '审计管理员(auadmin)', '系统管理员(sysadmin)', 'auadmin', 'sysadmin'
        ]
        if username == 'auadmin':
            queryset = queryset.filter(username__in=usernames)
        elif username == 'secadmin':
            queryset = queryset.exclude(username__in=usernames)
        return queryset
