import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import TicketHistory
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


class TestGrantITSupportRole:
    def test_manager_grant_it_support_role_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        requester = UserFactory(username="requester02", role=User.Role.REQUESTER)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            "/api/v1/it-supports/", {"user_id": str(requester.id)}
        )

        requester.refresh_from_db()
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == "requester02"
        assert response.data["current_ticket"] is None
        assert requester.role == User.Role.IT_SUPPORT

    def test_granted_support_can_open_queue_and_claim_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        api_client.post("/api/v1/it-supports/", {"user_id": str(requester.id)})
        requester.refresh_from_db()
        api_client.force_authenticate(user=requester)
        queue_response = api_client.get("/api/v1/tickets/queue/")
        claim_response = api_client.post(f"/api/v1/tickets/{ticket.id}/claim/")

        assert queue_response.status_code == status.HTTP_200_OK
        assert queue_response.data["results"][0]["id"] == str(ticket.id)
        assert claim_response.status_code == status.HTTP_200_OK
        assert claim_response.data["assignee"]["id"] == str(requester.id)

    def test_grant_role_to_existing_it_support_fails(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.post("/api/v1/it-supports/", {"user_id": str(support.id)})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_grant_role_to_manager_account_fails(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        other_manager = UserFactory(role=User.Role.IT_MANAGER)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            "/api/v1/it-supports/", {"user_id": str(other_manager.id)}
        )

        other_manager.refresh_from_db()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert other_manager.role == User.Role.IT_MANAGER

    def test_grant_role_to_unknown_user_fails(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)

        api_client.force_authenticate(user=manager)
        response = api_client.post(
            "/api/v1/it-supports/", {"user_id": str(uuid.uuid4())}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_support_cannot_grant_it_support_role(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=support)
        response = api_client.post(
            "/api/v1/it-supports/", {"user_id": str(requester.id)}
        )

        requester.refresh_from_db()
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert requester.role == User.Role.REQUESTER


class TestUpdateITSupport:
    def test_manager_update_support_username_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(username="binh", role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.patch(
            f"/api/v1/it-supports/{support.id}/", {"username": "binh.tran"}
        )

        support.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == "binh.tran"
        assert support.username == "binh.tran"

    def test_update_support_with_taken_username_fails(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        UserFactory(username="cuc.le", role=User.Role.IT_SUPPORT)
        support = UserFactory(username="binh", role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.patch(
            f"/api/v1/it-supports/{support.id}/", {"username": "CUC.LE"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "username" in response.data

    def test_support_cannot_update_another_support(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(username="binh", role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=support_a)
        response = api_client.patch(
            f"/api/v1/it-supports/{support_b.id}/", {"username": "doi.ten"}
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeactivateITSupport:
    def test_manager_deactivate_free_support_success(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")

        support.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False
        assert support.is_active is False

    def test_deactivated_support_cannot_log_in(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(
            username="itsupport02", password="Matkhau123", role=User.Role.IT_SUPPORT
        )

        api_client.force_authenticate(user=manager)
        api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")
        api_client.force_authenticate(user=None)
        response = api_client.post(
            "/api/v1/auth/token/",
            {"username": "itsupport02", "password": "Matkhau123"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivated_support_existing_tokens_stop_working(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(
            username="itsupport02", password="Matkhau123", role=User.Role.IT_SUPPORT
        )
        tokens = api_client.post(
            "/api/v1/auth/token/",
            {"username": "itsupport02", "password": "Matkhau123"},
        ).data

        api_client.force_authenticate(user=manager)
        api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")
        api_client.force_authenticate(user=None)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        access_response = api_client.get("/api/v1/tickets/")
        api_client.credentials()
        refresh_response = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}
        )

        assert access_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivated_support_is_not_in_assignable_list(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")
        response = api_client.get("/api/v1/it-supports/?is_active=true&available=true")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert str(support.id) not in returned_ids

    def test_handled_history_of_deactivated_support_is_kept(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=manager)
        api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")
        response = api_client.get(f"/api/v1/tickets/handled/?assignee={support.id}")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(ticket.id)]

    def test_cannot_deactivate_support_with_processing_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, title="Máy chủ in không phản hồi")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")

        support.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Máy chủ in không phản hồi" in response.data["detail"]
        assert support.is_active is True

    def test_cannot_deactivate_support_with_reopened_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/it-supports/{support.id}/deactivate/")

        support.refresh_from_db()
        assert response.status_code == status.HTTP_409_CONFLICT
        assert support.is_active is True

    def test_can_deactivate_after_transferring_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        api_client.post(
            f"/api/v1/tickets/{ticket.id}/reassign/",
            {"received_by": str(support_b.id), "reason": "Nhân sự nghỉ việc"},
        )
        response = api_client.post(f"/api/v1/it-supports/{support_a.id}/deactivate/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

    def test_support_cannot_deactivate_another_support(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=support_a)
        response = api_client.post(f"/api/v1/it-supports/{support_b.id}/deactivate/")

        support_b.refresh_from_db()
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert support_b.is_active is True

    def test_deactivate_requester_account_returns_404(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=manager)
        response = api_client.post(f"/api/v1/it-supports/{requester.id}/deactivate/")

        requester.refresh_from_db()
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert requester.is_active is True


class TestITSupportUnsupportedMethods:
    def test_it_support_account_cannot_be_deleted(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.delete(f"/api/v1/it-supports/{support.id}/")

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert User.objects.filter(pk=support.pk).exists()

    def test_it_support_cannot_be_replaced_with_put(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(username="binh", role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.put(
            f"/api/v1/it-supports/{support.id}/", {"username": "binh.tran"}
        )

        support.refresh_from_db()
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert support.username == "binh"
