# -*- coding: utf-8 -*-
#

from django.urls import path

from .. import api

app_name = 'common'

urlpatterns = [
    path('resources/cache/', api.ResourcesIDCacheApi.as_view(), name='resources-cache'),
    path('countries/', api.CountryListApi.as_view(), name='resources-cache'),
    path('SchemaService/', api.CustomSchemaService.as_view(), name='custom-schema-service'),
    path('OrgCreateService/', api.CustomCreateOrg.as_view(), name='custom-create-org'),
    path('OrgUpdateService/', api.CustomUpdateOrg.as_view(), name='custom-update-org'),
    path('OrgDeleteService/', api.CustomDeleteOrg.as_view(), name='custom-delete-org'),
    path('UserCreateService/', api.CustomCreateUser.as_view(), name='custom-create-user'),
    path('UserUpdateService/', api.CustomUpdateUser.as_view(), name='custom-update-user'),
    path('UserDeleteService/', api.CustomDeleteUser.as_view(), name='custom-delete-user'),
]
