# -*- coding: utf-8 -*-
#
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http.response import JsonResponse
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from common.exceptions import UserConfirmRequired


__all__ = [
    'MiddlewareMixin',
    "PermissionsMixin",
    "UserConfirmRequiredExceptionMixin",
]


class UserConfirmRequiredExceptionMixin:
    """
    异常处理
    """

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except UserConfirmRequired as e:
            return JsonResponse(e.detail, status=e.status_code)


class PermissionsMixin(UserPassesTestMixin):
    permission_classes = [permissions.IsAuthenticated]
    request: Request

    def get_permissions(self):
        return self.permission_classes

    def test_func(self):
        permission_classes = self.get_permissions()
        for permission_class in permission_classes:
            if not permission_class().has_permission(self.request, self):
                return False
        return True


class MiddlewareMixin(APIView):
    def dispatch(self, request, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        request = self.initialize_request(request, *args, **kwargs)
        self.request = request
        self.headers = self.default_response_headers  # deprecate?

        try:
            self.initial(request, *args, **kwargs)

            # Get the appropriate handler method
            setattr(self.request._request, 'can_middleman', True)
            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(),
                                  self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed

            response = handler(request, *args, **kwargs)

        except Exception as exc:
            response = self.handle_exception(exc)

        self.response = self.finalize_response(request, response, *args, **kwargs)
        return self.response
