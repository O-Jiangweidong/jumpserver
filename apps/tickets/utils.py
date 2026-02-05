# -*- coding: utf-8 -*-
#
from django.conf import settings

from common.utils import get_logger
from notifications.backends import BACKEND
from notifications.notifications import publish_task
from .notifications import TicketAppliedToAssigneeMessage, TicketProcessedToApplicantMessage

logger = get_logger(__file__)


def send_ticket_applied_mail_to_assignees(ticket, assignees):
    if not assignees:
        logger.debug(
            "Not found assignees, ticket: {}({}), assignees: {}".format(
                ticket, str(ticket.id), assignees
            )
        )
        return

    msgs = []
    for user in assignees:
        instance = TicketAppliedToAssigneeMessage(user, ticket)
        if settings.DEBUG:
            logger.debug(instance)
        instance.publish_async()
        msgs.append(instance)

    if len(msgs) > 0:
        msg_info = msgs[0].get_wecom_webhook_msg()
        receive_user_ids = [str(u.id) for u in assignees]
        backends_msg_mapper = {BACKEND.WECOM_WEBHOOK: msg_info}
        publish_task.delay(receive_user_ids, backends_msg_mapper)


def send_ticket_processed_mail_to_applicant(ticket, processor):
    if not ticket.applicant:
        logger.error("Not found applicant: {}({})".format(ticket.title, ticket.id))
        return

    instance = TicketProcessedToApplicantMessage(ticket.applicant, ticket, processor)
    if settings.DEBUG:
        logger.debug(instance)
    instance.publish_async()
