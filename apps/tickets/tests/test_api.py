import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import TicketHistory
from apps.tickets.tests.factories import (
    CategoryFactory,
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestTicketAuthentication:
    def test_list_tickets_requires_authentication(self, api_client):
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_ticket_requires_authentication(self, api_client):
        response = api_client.post("/api/v1/tickets/", {"title": "Lỗi máy in"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestTicketDataIsolationAndIDOR:
    def test_requester_only_sees_own_tickets(self, api_client):
        requester_1 = UserFactory(role=User.Role.REQUESTER)
        requester_2 = UserFactory(role=User.Role.REQUESTER)

        TicketFactory.create_batch(2, created_by=requester_1)
        TicketFactory.create_batch(3, created_by=requester_2)

        api_client.force_authenticate(user=requester_1)
        response = api_client.get("/api/v1/tickets/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_requester_cannot_access_other_user_ticket_detail(self, api_client):
        owner = UserFactory(role=User.Role.REQUESTER)
        stranger = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=owner)

        api_client.force_authenticate(user=stranger)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTicketCreationAPI:
    def test_create_ticket_success(self, api_client):
        user = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()

        api_client.force_authenticate(user=user)
        payload = {
            "title": "Màn hình máy tính không lên nguồn",
            "description": "Bật nút nguồn màn hình Dell chỉ nhấp nháy đèn cam rồi tắt hẳn.",
            "priority": "HIGH",
            "category": str(category.id),
        }

        response = api_client.post("/api/v1/tickets/", payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == payload["title"]
        assert response.data["priority"] == payload["priority"]

    def test_create_ticket_validation_title_too_short(self, api_client):
        user = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()

        api_client.force_authenticate(user=user)
        payload = {
            "title": "Lỗi",  # less than 5 characters
            "description": "Mô tả chi tiết sự cố...",
            "priority": "LOW",
            "category": str(category.id),
        }

        response = api_client.post("/api/v1/tickets/", payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data


class TestTicketActionsPermissions:
    def test_only_support_can_claim_ticket(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/claim/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_support_claim_ticket_success(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=support)
        response = api_client.post(f"/api/v1/tickets/{ticket.id}/claim/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING
        assert response.data["assignee"]["id"] == str(support.id)

    def test_only_manager_can_assign_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=None)

        api_client.force_authenticate(user=support)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/assign/", {"support_id": str(support.id)}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_assign_ticket_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            f"/api/v1/tickets/{ticket.id}/assign/",
            {"support_id": str(support.id)},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING
        assert response.data["assignee"]["id"] == str(support.id)
