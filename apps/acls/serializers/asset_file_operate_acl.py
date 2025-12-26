from orgs.mixins.serializers import BulkOrgResourceModelSerializer
from .base import BaseUserAssetAccountACLSerializer as BaseSerializer
from ..models import AssetFileOperateACL
from ..const import ActionChoices

__all__ = ["AssetFileOperateACLSerializer"]


class AssetFileOperateACLSerializer(BaseSerializer, BulkOrgResourceModelSerializer):
    class Meta(BaseSerializer.Meta):
        model = AssetFileOperateACL
        fields = BaseSerializer.Meta.fields + ['reviewers_2']
        action_choices_exclude = [
            ActionChoices.accept,
            ActionChoices.notice,
            ActionChoices.warning,
            ActionChoices.notify_and_warn,
            ActionChoices.face_online,
            ActionChoices.face_verify,
            ActionChoices.change_secret
        ]
