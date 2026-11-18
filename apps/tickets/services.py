from django.db import transaction
from django.core.exceptions import ValidationError

from apps.tickets.models import Ticket, TicketHistory, AssignmentHistory
from apps.users.models import User


class TicketAlreadyCloseError(ValidationError):
    pass


@transaction.atomic
def claim_ticket(ticket_id, support_user: User) -> Ticket:
    """
    IT Support claim ticket from queue (NEW -> PROCESSING).
    """
    # Lock row
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    # Check assignee
    if ticket.assignee is not None:
        raise ValidationError("Ticket has been assigned.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status != TicketHistory.Status.NEW:
        raise ValidationError("Only ticket in NEW status can be accepted.")

    # Claim
    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    # Change ticket status: PROCESSING
    TicketHistory.objects.create(
        ticket=ticket,
        status=TicketHistory.Status.PROCESSING,
    )

    return ticket


@transaction.atomic
def reassign_ticket(ticket_id, sent_by: User, received_by: User, reason: str) -> Ticket:
    """
    Transfer the ticket to another IT Support.
    """
    if not reason.strip():
        raise ValidationError("Reason is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is None:
        raise ValidationError(
            "Ticket has not been assigned yet. Use claim or assign instead."
        )

    if ticket.assignee == received_by:
        raise ValidationError("Cannot reassign ticket to the current assignee.")

    latest_history = ticket.status_history.first()
    terminal_statuses = [
        TicketHistory.Status.CLOSED,
        TicketHistory.Status.CANCELLED,
        TicketHistory.Status.REJECTED,
    ]
    if latest_history and latest_history.status in terminal_statuses:
        raise ValidationError(
            f"Cannot reassign a ticket that is already {latest_history.status}."
        )

    # Change assignee
    ticket.assignee = received_by
    ticket.save(update_fields=["assignee"])

    # Write history change log
    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=sent_by,
        received_by=received_by,
        reason=reason,
    )

    return ticket


@transaction.atomic
def assign_ticket(ticket_id, support_user: User, assigned_by: User) -> Ticket:
    """
    Manager assigns a NEW ticket to an IT Support (NEW -> PROCESSING).
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is not None:
        raise ValidationError("Ticket has already been assigned. Use reassign instead.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status not in [
        TicketHistory.Status.NEW,
        TicketHistory.Status.REOPEN,
    ]:
        raise ValidationError("Only tickets in NEW or REOPEN status can be assigned.")

    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    TicketHistory.objects.create(
        ticket=ticket,
        status=TicketHistory.Status.PROCESSING,
    )

    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=assigned_by,
        received_by=support_user,
        reason="Initial assignment by Manager.",
    )

    return ticket


@transaction.atomic
def solve_ticket(ticket_id, support_user: User) -> Ticket:
    """
    IT Support marks the ticket as resolved (PROCESSING -> SOLVED).
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee != support_user and not support_user.is_superuser:
        raise ValidationError(
            "Only the person assigned to handle a ticket has the authority to mark it as complete."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.PROCESSING:
        raise ValidationError(
            "Only tickets in the PROCESSING state can be marked as SOLVED."
        )

    TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.SOLVED)

    return ticket


@transaction.atomic
def reject_ticket(ticket_id, support_user: User, reason: str) -> Ticket:
    """
    IT Support rejects an invalid ticket (NEW -> REJECTED).
    """
    if not reason.strip():
        raise ValidationError("A reason for refusal is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.NEW:
        raise ValidationError("Only tickets in the NEW status can be rejected.")

    ticket.note = f"[REJECTED by {support_user.username}]: {reason.strip()}"
    ticket.save(update_fields=["note"])
    TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.REJECTED)

    return ticket


@transaction.atomic
def close_ticket(ticket_id, requester_user: User) -> Ticket:
    """
    Requester confirms ticket closure (SOLVED -> CLOSED)
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.created_by != requester_user and not requester_user.is_superuser:
        raise ValidationError(
            "Only the person who created the ticket has the authority to confirm its closure."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.SOLVED:
        raise ValidationError(
            "Only tickets that have been resolved (SOLVED) can be closed."
        )

    TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.CLOSED)

    return ticket


@transaction.atomic
def reopen_ticket(ticket_id, requester_user: User, reason: str) -> Ticket:
    """
    The requester reopens the ticket if the issue has not been fully resolved (SOLVED -> REOPEN).
    """
    if not reason.strip():
        raise ValidationError("A reason for reopen is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.created_by != requester_user and not requester_user.is_superuser:
        raise ValidationError(
            "Only the person who created the ticket has the authority to reopen it."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.SOLVED:
        raise ValidationError("Only tickets with a status of SOLVED can be reopened.")

    TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.REOPEN)
    return ticket


@transaction.atomic
def cancel_ticket(ticket_id, requester_user: User) -> Ticket:
    """
    The requester cancels the request while it is still in the queue (NEW -> CANCELLED).
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.created_by != requester_user and not requester_user.is_superuser:
        raise ValidationError(
            "Only the person who created the ticket has the authority to cancel it."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.NEW:
        raise ValidationError("Only tickets with a status of NEW can be cancel.")

    TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.CANCELLED)

    return ticket
