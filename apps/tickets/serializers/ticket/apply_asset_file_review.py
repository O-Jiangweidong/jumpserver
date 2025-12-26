from tickets.models import ApplyAssetFileTicket
from .ticket import TicketApplySerializer

__all__ = [
    'ApplyAssetFileReviewSerializer'
]


class ApplyAssetFileReviewSerializer(TicketApplySerializer):
    class Meta:
        model = ApplyAssetFileTicket
        writeable_fields = ['apply_login_user', 'apply_login_asset', 'apply_login_account']
        fields = TicketApplySerializer.Meta.fields + writeable_fields + ['meta']
