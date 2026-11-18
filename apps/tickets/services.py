from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.tickets.models import (
    AssignmentHistory,
    AttachmentComment,
    Comment,
    Ticket,
    TicketHistory,
)
from apps.tickets.selectors import (
    TERMINAL_STATUSES,
    get_current_status,
    get_solved_tickets_to_auto_close,
    is_solved_window_expired,
    is_support_busy,
)
from apps.users.models import User


class TicketAlreadyCloseError(ValidationError):
    pass


class TicketConflictError(ValidationError):
    """
    The request is valid but conflicts with the current state of the ticket
    (busy IT Support, expired reopen window, locked comments...). Mapped to 409.
    """


def _is_staff_override(user: User) -> bool:
    return bool(user.is_superuser or user.role == User.Role.IT_MANAGER)


def _lock_users(*users) -> None:
    """
    Lock IT Support rows (stable order to avoid deadlocks) so that the
    "max 1 PROCESSING ticket per IT Support" rule cannot be bypassed by
    concurrent requests.
    """
    ids = sorted({u.pk for u in users if u is not None}, key=str)

    if ids:
        list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


def _set_status(ticket: Ticket, status: str) -> TicketHistory:
    return TicketHistory.objects.create(ticket=ticket, status=status)


def _ensure_active_support(user: User, message: str) -> None:
    if user is None or not user.is_active or user.role != User.Role.IT_SUPPORT:
        raise ValidationError(message)


@transaction.atomic
def claim_ticket(ticket_id, support_user: User) -> Ticket:
    # Lock row
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    # Check assignee
    if ticket.assignee is not None:
        raise ValidationError("Ticket has been assigned.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status != TicketHistory.Status.NEW:
        raise ValidationError("Only ticket in NEW status can be accepted.")

    _lock_users(support_user)
    if is_support_busy(support_user):
        raise TicketConflictError(
            "You are already handling a PROCESSING ticket. "
            "Please resolve it before claiming a new one."
        )

    # Claim
    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    # Change ticket status: PROCESSING
    _set_status(ticket, TicketHistory.Status.PROCESSING)

    return ticket


@transaction.atomic
def reassign_ticket(ticket_id, sent_by: User, received_by: User, reason: str) -> Ticket:
    if not reason or not reason.strip():
        raise ValidationError("Reason is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is None:
        raise ValidationError(
            "Ticket has not been assigned yet. Use claim or assign instead."
        )

    if not _is_staff_override(sent_by) and ticket.assignee_id != sent_by.pk:
        raise PermissionDenied(
            "You can only transfer tickets that are currently assigned to you."
        )

    if ticket.assignee == received_by:
        raise ValidationError("Cannot reassign ticket to the current assignee.")

    _ensure_active_support(
        received_by, "The receiver must be an active IT Support account."
    )

    current_status = get_current_status(ticket)

    if current_status in TERMINAL_STATUSES:
        raise ValidationError(
            f"Cannot reassign a ticket that is already {current_status}."
        )

    if current_status not in (
        TicketHistory.Status.PROCESSING,
        TicketHistory.Status.REOPEN,
    ):
        raise TicketConflictError(
            "Only tickets in PROCESSING or REOPEN status can be reassigned."
        )

    _lock_users(ticket.assignee, received_by)

    # A REOPEN ticket keeps its status: the receiver resumes it when ready.
    if current_status == TicketHistory.Status.PROCESSING and is_support_busy(
        received_by
    ):
        raise TicketConflictError(
            "The receiver is currently handling another PROCESSING ticket."
        )

    # Change assignee
    ticket.assignee = received_by
    ticket.save(update_fields=["assignee"])

    # Write history change log
    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=sent_by,
        received_by=received_by,
        reason=reason.strip(),
    )

    return ticket


@transaction.atomic
def assign_ticket(ticket_id, support_user: User, assigned_by: User) -> Ticket:
    _ensure_active_support(
        support_user, "Cannot assign ticket to an inactive or non IT Support account."
    )

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is not None:
        raise ValidationError("Ticket has already been assigned. Use reassign instead.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status not in [
        TicketHistory.Status.NEW,
        TicketHistory.Status.REOPEN,
    ]:
        raise ValidationError("Only tickets in NEW or REOPEN status can be assigned.")

    _lock_users(support_user)
    support_busy = is_support_busy(support_user)
    if support_busy and latest_history.status == TicketHistory.Status.NEW:
        raise TicketConflictError(
            "The selected IT Support is currently handling another PROCESSING ticket."
        )

    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    if not support_busy:
        _set_status(ticket, TicketHistory.Status.PROCESSING)

    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=assigned_by,
        received_by=support_user,
        reason="Initial assignment by Manager.",
    )

    return ticket


@transaction.atomic
def solve_ticket(ticket_id, support_user: User) -> Ticket:
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

    _set_status(ticket, TicketHistory.Status.SOLVED)

    return ticket


@transaction.atomic
def reject_ticket(ticket_id, support_user: User, reason: str) -> Ticket:
    if not reason or not reason.strip():
        raise ValidationError("A reason for refusal is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    current_status = get_current_status(ticket)

    if current_status not in (
        TicketHistory.Status.NEW,
        TicketHistory.Status.PROCESSING,
    ):
        raise ValidationError(
            "Only tickets in the NEW or PROCESSING status can be rejected."
        )

    if (
        current_status == TicketHistory.Status.PROCESSING
        and not _is_staff_override(support_user)
        and ticket.assignee_id != support_user.pk
    ):
        raise PermissionDenied(
            "Only the assigned IT Support can reject a ticket that is being processed."
        )

    ticket.note = f"[REJECTED by {support_user.username}]: {reason.strip()}"
    ticket.save(update_fields=["note"])
    _set_status(ticket, TicketHistory.Status.REJECTED)

    return ticket


@transaction.atomic
def close_ticket(ticket_id, requester_user: User) -> Ticket:
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

    _set_status(ticket, TicketHistory.Status.CLOSED)

    return ticket


def auto_close_solved_tickets(now=None) -> int:
    """
    close every ticket that has stayed SOLVED for more than 48 hours(counted from the latest SOLVED transition).
    """
    candidate_ids = list(
        get_solved_tickets_to_auto_close(now).values_list("pk", flat=True)
    )
    closed = 0

    for ticket_id in candidate_ids:
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

            if get_current_status(ticket) != TicketHistory.Status.SOLVED:
                continue
            if not is_solved_window_expired(ticket, now):
                continue

            _set_status(ticket, TicketHistory.Status.CLOSED)
            closed += 1

    return closed


@transaction.atomic
def reopen_ticket(ticket_id, requester_user: User, reason: str) -> Ticket:
    if not reason or not reason.strip():
        raise ValidationError("A reason for reopen is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.created_by != requester_user and not requester_user.is_superuser:
        raise ValidationError(
            "Only the person who created the ticket has the authority to reopen it."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.SOLVED:
        raise ValidationError("Only tickets with a status of SOLVED can be reopened.")

    if is_solved_window_expired(ticket):
        raise TicketConflictError(
            "The 48-hour reopen window has expired. Please create a new ticket."
        )

    ticket.note = f"[REOPENED by {requester_user.username}]: {reason.strip()}"
    ticket.save(update_fields=["note"])
    _set_status(ticket, TicketHistory.Status.REOPEN)

    return ticket


@transaction.atomic
def resume_ticket(ticket_id, support_user: User) -> Ticket:
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is None:
        raise ValidationError("Ticket has no assignee. Use assign instead.")

    if not support_user.is_superuser and ticket.assignee_id != support_user.pk:
        raise PermissionDenied("Only the assigned IT Support can resume this ticket.")

    if get_current_status(ticket) != TicketHistory.Status.REOPEN:
        raise TicketConflictError("Only tickets in REOPEN status can be resumed.")

    _lock_users(ticket.assignee)
    if is_support_busy(ticket.assignee):
        raise TicketConflictError(
            "You are already handling a PROCESSING ticket. "
            "Please resolve it before resuming another one."
        )

    _set_status(ticket, TicketHistory.Status.PROCESSING)

    return ticket


@transaction.atomic
def cancel_ticket(ticket_id, requester_user: User) -> Ticket:
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.created_by != requester_user and not requester_user.is_superuser:
        raise ValidationError(
            "Only the person who created the ticket has the authority to cancel it."
        )

    latest = ticket.status_history.first()

    if not latest or latest.status != TicketHistory.Status.NEW:
        raise ValidationError("Only tickets with a status of NEW can be cancel.")

    _set_status(ticket, TicketHistory.Status.CANCELLED)

    return ticket


REQUESTER_EDITABLE_FIELDS = frozenset({"title", "description", "category", "priority"})
STAFF_EDITABLE_FIELDS = frozenset({"priority"})
SUPPORT_EDITABLE_STATUSES = (
    TicketHistory.Status.PROCESSING,
    TicketHistory.Status.SOLVED,
    TicketHistory.Status.REOPEN,
)


def validate_ticket_update(ticket: Ticket, user: User, fields) -> None:
    """
    Who may edit which fields of a ticket, depending on its status:

    | Status                      | Role                | Editable fields                         |
    |-----------------------------|---------------------|-----------------------------------------|
    | NEW                         | Requester (owner)   | title, description, category, priority  |
    | any non-final status        | IT Manager          | priority                                |
    | PROCESSING, SOLVED, REOPEN  | Assigned IT Support | priority                                |
    | CLOSED, REJECTED, CANCELLED | nobody              |                                         |
    """
    fields = set(fields)
    current_status = get_current_status(ticket)

    if current_status in TERMINAL_STATUSES:
        raise TicketConflictError(
            "This ticket is already finished and can no longer be edited."
        )

    if user.is_superuser:
        allowed = REQUESTER_EDITABLE_FIELDS
    elif user.role == User.Role.IT_MANAGER:
        allowed = STAFF_EDITABLE_FIELDS
    elif user.role == User.Role.IT_SUPPORT:
        if ticket.assignee_id != user.pk:
            raise PermissionDenied(
                "Only the assigned IT Support can change the priority of this ticket."
            )
        if current_status not in SUPPORT_EDITABLE_STATUSES:
            raise TicketConflictError(
                "The priority can only be changed while the ticket is "
                "PROCESSING, SOLVED or REOPEN."
            )
        allowed = STAFF_EDITABLE_FIELDS
    else:
        if ticket.created_by_id != user.pk:
            raise PermissionDenied("You can only edit your own tickets.")

        if current_status != TicketHistory.Status.NEW:
            raise TicketConflictError(
                "Ticket has already been claimed and can no longer be edited."
            )
        allowed = REQUESTER_EDITABLE_FIELDS

    not_allowed = fields - allowed
    if not_allowed:
        raise PermissionDenied(
            f"You are not allowed to update: {', '.join(sorted(not_allowed))}."
        )


def validate_comment_permission(ticket: Ticket, author: User) -> None:
    """
    | Status                              | Who can comment                    |
    |-------------------------------------|------------------------------------|
    | NEW                                 | any IT Support + ticket owner      |
    | PROCESSING, REOPEN, SOLVED (<= 48h) | assigned IT Support + ticket owner |
    | CLOSED, REJECTED, CANCELLED         | nobody (comments locked)           |

    IT Manager can only read comments.
    """
    current_status = get_current_status(ticket)

    if not author.is_superuser:
        if author.role == User.Role.IT_MANAGER:
            raise PermissionDenied("IT Managers can only view comments.")
        if author.role == User.Role.IT_SUPPORT:
            if (
                current_status != TicketHistory.Status.NEW
                and ticket.assignee_id != author.pk
            ):
                raise PermissionDenied(
                    "Only the assigned IT Support can comment on this ticket."
                )
        elif ticket.created_by_id != author.pk:
            raise PermissionDenied("You can only comment on your own tickets.")

    if current_status in TERMINAL_STATUSES or (
        current_status == TicketHistory.Status.SOLVED
        and is_solved_window_expired(ticket)
    ):
        raise TicketConflictError(
            "Comments are locked because this ticket has been finished."
        )


@transaction.atomic
def create_comment(ticket: Ticket, author: User, content: str, attachment=None):
    validate_comment_permission(ticket, author)

    comment = Comment.objects.create(ticket=ticket, author=author, content=content)

    if attachment:
        AttachmentComment.objects.create(
            comment=comment, url=attachment, size=attachment.size
        )

    return comment
