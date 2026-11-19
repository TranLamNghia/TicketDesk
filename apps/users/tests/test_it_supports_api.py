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


class TestListITSupports:
    def test_manager_list_only_active_and_available_supports(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        free_support = UserFactory(role=User.Role.IT_SUPPORT)
        busy_support = UserFactory(role=User.Role.IT_SUPPORT)
        UserFactory(role=User.Role.IT_SUPPORT, is_active=False)
        ticket = TicketFactory(assignee=busy_support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/?is_active=true&available=true")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert response.status_code == status.HTTP_200_OK
        assert returned_ids == [str(free_support.id)]

    def test_support_holding_only_reopened_ticket_is_still_available(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/?available=true")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert str(support.id) in returned_ids

    def test_list_shows_current_processing_ticket_of_busy_support(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, title="Máy tính không vào được mạng")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/")

        assert response.data["results"][0]["current_ticket"] == {
            "id": str(ticket.id),
            "title": "Máy tính không vào được mạng",
        }

    def test_free_support_has_no_current_ticket(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/")

        assert response.data["results"][0]["current_ticket"] is None

    def test_filter_busy_supports(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        UserFactory(role=User.Role.IT_SUPPORT)
        busy_support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=busy_support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/?available=false")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(busy_support.id)]

    def test_filter_inactive_supports(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        UserFactory(role=User.Role.IT_SUPPORT)
        inactive_support = UserFactory(role=User.Role.IT_SUPPORT, is_active=False)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/?is_active=false")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(inactive_support.id)]

    def test_search_supports_by_username(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        target = UserFactory(username="binh.tran", role=User.Role.IT_SUPPORT)
        UserFactory(username="cuc.le", role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/?search=binh")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(target.id)]

    def test_list_does_not_include_other_roles(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/it-supports/")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(support.id)]

    def test_support_can_list_colleagues_for_transfer(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)

        api_client.force_authenticate(user=support_a)
        response = api_client.get("/api/v1/it-supports/?is_active=true&available=true")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert response.status_code == status.HTTP_200_OK
        assert str(support_b.id) in returned_ids

    def test_requester_cannot_list_supports(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=requester)
        response = api_client.get("/api/v1/it-supports/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_supports_requires_authentication(self, api_client):
        response = api_client.get("/api/v1/it-supports/")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
