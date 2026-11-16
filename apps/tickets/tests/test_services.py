import pytest
from django.core.exceptions import ValidationError

from apps.tickets.models import TicketHistory, AssignmentHistory
from apps.tickets.services import claim_ticket, assign_ticket, reassign_ticket
from apps.tickets.tests.factories import (
    TicketFactory,
    UserFactory,
    TicketHistoryFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


class TestClaimTicket:
    def test_claim_ticket_success(self):
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        updated_ticket = claim_ticket(ticket.id, support)

        assert updated_ticket.assignee == support
        latest_history = updated_ticket.status_history.first()
        assert latest_history.status == TicketHistory.Status.PROCESSING

    def test_cannot_claim_already_assigned_ticket(self):
        existing_support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=existing_support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        new_support = UserFactory(role=User.Role.IT_SUPPORT)

        with pytest.raises(ValidationError, match="Ticket has been assigned"):
            claim_ticket(ticket.id, new_support)

    def test_cannot_claim_non_new_ticket(self):
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.PROCESSING
        )  # assuming the status is "processing"
        support = UserFactory(role=User.Role.IT_SUPPORT)

        with pytest.raises(
            ValidationError, match="Only ticket in NEW status can be accepted."
        ):
            claim_ticket(ticket.id, support)


class TestAssignTicket:
    def test_assign_ticket_success(self):
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        updated_ticket = assign_ticket(ticket.id, support, manager)

        assert updated_ticket.assignee == support
        assert (
            updated_ticket.status_history.first().status
            == TicketHistory.Status.PROCESSING
        )

        log = AssignmentHistory.objects.filter(ticket=ticket).first()

        assert log is not None
        assert log.sent_by == manager
        assert log.received_by == support

    def test_assign_reopened_ticket_success(self):
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        updated_ticket = assign_ticket(ticket.id, support, manager)

        assert updated_ticket.assignee == support
        assert (
            updated_ticket.status_history.first().status
            == TicketHistory.Status.PROCESSING
        )

    def test_cannot_assign_already_assigned_ticket(self):
        support1 = UserFactory(role=User.Role.IT_SUPPORT)
        support2 = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support1)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        manager = UserFactory(role=User.Role.IT_MANAGER)

        with pytest.raises(ValidationError, match="Ticket has already been assigned."):
            assign_ticket(ticket.id, support2, manager)


class TestReassignTicket:
    def test_reassign_ticket_success(self):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        manager = UserFactory(role=User.Role.IT_MANAGER)
        updated_ticket = reassign_ticket(
            ticket.id,
            sent_by=manager,
            received_by=support_b,
            reason="Afternoon shift handover",
        )

        assert updated_ticket.assignee == support_b

        log = AssignmentHistory.objects.filter(ticket=ticket).first()

        assert log.sent_by == manager
        assert log.received_by == support_b
        assert log.reason == "Afternoon shift handover"

    def test_cannot_reassign_without_reason(self):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        manager = UserFactory(role=User.Role.IT_MANAGER)

        with pytest.raises(ValidationError, match="Reason is required."):
            reassign_ticket(ticket.id, manager, support_b, reason="   ")

    def test_cannot_reassign_unassigned_ticket(self):
        ticket = TicketFactory(assignee=None)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        manager = UserFactory(role=User.Role.IT_MANAGER)

        with pytest.raises(ValidationError, match="Ticket has not been assigned yet."):
            reassign_ticket(ticket.id, manager, support, reason="Lý do")

    def test_cannot_reassign_to_same_assignee(self):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        manager = UserFactory(role=User.Role.IT_MANAGER)

        with pytest.raises(
            ValidationError, match="Cannot reassign ticket to the current assignee."
        ):
            reassign_ticket(ticket.id, manager, support, reason="Lý do")

    def test_cannot_reassign_closed_ticket(self):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)
        manager = UserFactory(role=User.Role.IT_MANAGER)

        with pytest.raises(
            ValidationError, match="Cannot reassign a ticket that is already CLOSED."
        ):
            reassign_ticket(ticket.id, manager, support_b, reason="Lý do")
