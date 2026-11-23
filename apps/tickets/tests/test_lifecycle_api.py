from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import AssignmentHistory, TicketHistory
from apps.tickets.services import auto_close_solved_tickets
from apps.tickets.tests.factories import (
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestClaimTicketWorkload:
    def test_busy_support_cannot_claim_another_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        current_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(
            ticket=current_ticket, status=TicketHistory.Status.PROCESSING
        )
        new_ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=new_ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{new_ticket.id}/claim/")

        new_ticket.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert new_ticket.assignee is None
        assert new_ticket.status_history.first().status == TicketHistory.Status.NEW

    def test_support_can_claim_again_after_solving_current_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        solved_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=solved_ticket, status=TicketHistory.Status.SOLVED)
        new_ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=new_ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{new_ticket.id}/claim/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING


class TestAssignTicketRules:
    def test_manager_cannot_assign_ticket_to_inactive_support(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        inactive_support = UserFactory(role=User.Role.IT_SUPPORT, is_active=False)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/assign/",
            {"support_id": str(inactive_support.id)},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert ticket.assignee is None
        assert ticket.status_history.first().status == TicketHistory.Status.NEW

    def test_manager_cannot_assign_new_ticket_to_busy_support(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        current_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(
            ticket=current_ticket, status=TicketHistory.Status.PROCESSING
        )
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/assign/", {"support_id": str(support.id)}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.assignee is None


class TestReopenTicketWindow:
    def test_requester_reopen_ticket_within_48_hours_keeps_assignee(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=10)
        )

        api_client.force_authenticate(user=requester)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reopen/", {"reason": "Mạng vẫn chập chờn"}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.REOPEN
        assert ticket.assignee == support
        assert "Mạng vẫn chập chờn" in ticket.note

    def test_requester_cannot_reopen_ticket_after_48_hours(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=49)
        )

        api_client.force_authenticate(user=requester)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reopen/", {"reason": "Sự cố tái diễn"}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED

    def test_reopened_ticket_stays_reopen_even_when_support_is_free(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=requester)
        api_client.post(f"/api/v1/tickets/{ticket.id}/reopen/", {"reason": "Lỗi lại"})

        assert ticket.status_history.first().status == TicketHistory.Status.REOPEN


class TestResumeReopenedTicket:
    def test_support_resume_reopened_ticket_success(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/resume/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING

    def test_busy_support_cannot_resume_reopened_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        current_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(
            ticket=current_ticket, status=TicketHistory.Status.PROCESSING
        )
        reopened_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=reopened_ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{reopened_ticket.id}/resume/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (
            reopened_ticket.status_history.first().status == TicketHistory.Status.REOPEN
        )

    def test_solving_current_ticket_does_not_resume_reopened_ticket_automatically(
        self, api_client
    ):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        current_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(
            ticket=current_ticket, status=TicketHistory.Status.PROCESSING
        )
        reopened_ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=reopened_ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=support)
        api_client.post(f"/api/v1/tickets/{current_ticket.id}/solve/")

        assert (
            reopened_ticket.status_history.first().status == TicketHistory.Status.REOPEN
        )

    def test_other_support_cannot_resume_ticket(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=support_b)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/resume/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.status_history.first().status == TicketHistory.Status.REOPEN

    def test_manager_cannot_resume_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/resume/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_resume_ticket_that_is_not_reopen(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/resume/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED


class TestSupportTransferTicket:
    def test_support_transfer_own_ticket_to_colleague_success(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_a)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {
                "received_by": str(support_b.id),
                "reason": "Lỗi mạng, cần người chuyên mạng",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["assignee"]["id"] == str(support_b.id)

        log = AssignmentHistory.objects.filter(ticket=ticket).first()

        assert log.sent_by == support_a
        assert log.received_by == support_b
        assert log.reason == "Lỗi mạng, cần người chuyên mạng"
        assert log.assigned_at is not None

    def test_support_cannot_transfer_ticket_of_another_support(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_b)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_a)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(support_a.id), "reason": "Để mình xử lý"},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.assignee == support_b

    def test_support_cannot_transfer_ticket_without_reason(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_a)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(support_b.id), "reason": "   "},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "reason" in response.data
        assert ticket.assignee == support_a

    def test_cannot_transfer_processing_ticket_to_busy_support(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        busy_ticket = TicketFactory(assignee=support_b)
        TicketHistoryFactory(ticket=busy_ticket, status=TicketHistory.Status.PROCESSING)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_a)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(support_b.id), "reason": "Bàn giao ca"},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.assignee == support_a

    def test_cannot_transfer_ticket_to_inactive_support(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        inactive_support = UserFactory(role=User.Role.IT_SUPPORT, is_active=False)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(inactive_support.id), "reason": "Bàn giao ca"},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert ticket.assignee == support

    def test_transfer_reopened_ticket_keeps_reopen_status(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(support_b.id), "reason": "Bàn giao ca"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert ticket.status_history.first().status == TicketHistory.Status.REOPEN


class TestRejectTicketRules:
    def test_manager_reject_duplicate_ticket_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reject/", {"reason": "Duplicate"}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.REJECTED
        assert "Duplicate" in ticket.note

    def test_support_reject_own_processing_ticket_success(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reject/",
            {"reason": "Thiết bị cá nhân không thuộc diện hỗ trợ"},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.REJECTED
        assert "Thiết bị cá nhân không thuộc diện hỗ trợ" in ticket.note

    def test_other_support_cannot_reject_processing_ticket(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_b)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reject/", {"reason": "Không hợp lệ"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.status_history.first().status == TicketHistory.Status.PROCESSING

    def test_cannot_reject_solved_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=support)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/reject/", {"reason": "Sai phạm vi"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED


class TestCloseAndCancelPermissions:
    def test_support_cannot_close_solved_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/close/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED

    def test_manager_cannot_close_solved_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory()
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/close/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED

    def test_requester_cannot_cancel_solved_ticket(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=requester)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/cancel/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED

    def test_requester_cancel_reopened_ticket_success(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=requester)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/cancel/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.CANCELLED

    def test_cancelling_processing_ticket_frees_the_support(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        processing_ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(
            ticket=processing_ticket, status=TicketHistory.Status.PROCESSING
        )
        next_ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=next_ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        api_client.post(f"/api/v1/tickets/{processing_ticket.id}/cancel/")
        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{next_ticket.id}/claim/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING


class TestAutoCloseSolvedTickets:
    def test_auto_close_ticket_solved_more_than_48_hours(self):
        ticket = TicketFactory()
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=49)
        )

        closed = auto_close_solved_tickets()

        assert closed == 1
        assert ticket.status_history.first().status == TicketHistory.Status.CLOSED

    def test_auto_close_ignores_recently_solved_ticket(self):
        ticket = TicketFactory()
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=10)
        )

        closed = auto_close_solved_tickets()

        assert closed == 0
        assert ticket.status_history.first().status == TicketHistory.Status.SOLVED

    def test_auto_close_ignores_reopened_ticket(self):
        ticket = TicketFactory()
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.REOPEN
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(days=5)
        )

        closed = auto_close_solved_tickets()

        assert closed == 0
        assert ticket.status_history.first().status == TicketHistory.Status.REOPEN

    def test_auto_close_does_not_close_the_same_ticket_twice(self):
        ticket = TicketFactory()
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=49)
        )

        assert auto_close_solved_tickets() == 1
        assert auto_close_solved_tickets() == 0
        assert (
            ticket.status_history.filter(status=TicketHistory.Status.CLOSED).count()
            == 1
        )

    def test_auto_close_command_reports_number_of_closed_tickets(self):
        for hours in (49, 72):
            ticket = TicketFactory()
            history = TicketHistoryFactory(
                ticket=ticket, status=TicketHistory.Status.SOLVED
            )
            TicketHistory.objects.filter(pk=history.pk).update(
                update_status_at=timezone.now() - timedelta(hours=hours)
            )
        output = StringIO()

        call_command("auto_close_solved_tickets", stdout=output)

        assert "Auto-closed 2 ticket(s)." in output.getvalue()
