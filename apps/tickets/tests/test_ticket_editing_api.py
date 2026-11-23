import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import Ticket, TicketHistory
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


class TestRequesterEditTicket:
    def test_requester_edit_description_of_new_ticket_success(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/",
            {"description": "Đã thử cắm lại nguồn nhưng đèn vẫn báo đỏ"},
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert ticket.description == "Đã thử cắm lại nguồn nhưng đèn vẫn báo đỏ"

    def test_requester_change_priority_of_new_ticket_success(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester, priority="LOW")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"priority": "HIGH"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["priority"] == "HIGH"

    def test_requester_cannot_edit_ticket_after_it_is_claimed(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(
            created_by=requester, assignee=support, title="Máy in tầng 2 bị kẹt giấy"
        )
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=requester)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"title": "Tiêu đề đã bị sửa đổi"}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.title == "Máy in tầng 2 bị kẹt giấy"

    def test_requester_cannot_edit_ticket_of_another_requester(self, api_client):
        requester_1 = UserFactory(role=User.Role.REQUESTER)
        requester_2 = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester_2)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester_1)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"title": "Sửa ticket người khác"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_change_ticket_status_through_update(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"status": TicketHistory.Status.CLOSED}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.status_history.first().status == TicketHistory.Status.NEW


class TestSupportAndManagerChangePriority:
    def test_support_change_priority_of_own_ticket_success(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"priority": "MEDIUM"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["priority"] == "MEDIUM"

    def test_support_cannot_change_priority_of_another_support_ticket(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_b, priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_a)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"priority": "LOW"}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert ticket.priority == "HIGH"

    def test_support_cannot_edit_ticket_title(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"title": "Tiêu đề mới của support"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_raise_priority_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, priority="LOW")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"priority": "URGENT"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["priority"] == "URGENT"

    def test_manager_cannot_edit_ticket_title(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory()
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"title": "Tiêu đề mới của manager"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_edit_finished_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority="LOW")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=manager)
        response = api_client.patch(
            f"/api/v1/tickets/{ticket.id}/", {"priority": "URGENT"}
        )

        ticket.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert ticket.priority == "LOW"


class TestTicketDeletion:
    def test_requester_cannot_delete_own_ticket(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        response = api_client.delete(f"/api/v1/tickets/{ticket.id}/")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert Ticket.objects.filter(pk=ticket.pk).exists()

    def test_manager_cannot_delete_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory()
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=manager)
        response = api_client.delete(f"/api/v1/tickets/{ticket.id}/")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert Ticket.objects.filter(pk=ticket.pk).exists()
