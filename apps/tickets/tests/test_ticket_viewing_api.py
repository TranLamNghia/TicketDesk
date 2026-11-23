from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import Ticket, TicketHistory
from apps.tickets.tests.factories import (
    CategoryFactory,
    CommentFactory,
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestTicketDetail:
    def test_requester_detail_shows_assignee_comments_and_status_history(
        self, api_client
    ):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(username="itsupport01", role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        CommentFactory.create_batch(2, ticket=ticket)

        api_client.force_authenticate(user=requester)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        statuses = [item["status"] for item in response.data["status_history"]]
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.PROCESSING
        assert response.data["assignee"]["username"] == "itsupport01"
        assert len(response.data["comments"]) == 2
        assert TicketHistory.Status.NEW in statuses
        assert TicketHistory.Status.PROCESSING in statuses

    def test_support_view_detail_of_handled_closed_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)
        CommentFactory.create_batch(3, ticket=ticket)

        api_client.force_authenticate(user=support)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TicketHistory.Status.CLOSED
        assert len(response.data["comments"]) == 3
        assert len(response.data["status_history"]) == 3


class TestTicketListFilters:
    def test_filter_tickets_by_category(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        network = CategoryFactory(name="Phần cứng/Mạng")
        software = CategoryFactory(name="Phần mềm")
        network_tickets = TicketFactory.create_batch(2, category=network)
        TicketFactory.create_batch(3, category=software)

        api_client.force_authenticate(user=support)
        response = api_client.get(f"/api/v1/tickets/?category={network.id}")

        returned_ids = {item["id"] for item in response.data["results"]}
        assert response.status_code == status.HTTP_200_OK
        assert returned_ids == {str(ticket.id) for ticket in network_tickets}

    def test_manager_list_tickets_of_all_supports(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        TicketFactory(assignee=support_a)
        TicketFactory(assignee=support_b)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/")

        assignee_ids = {item["assignee"]["id"] for item in response.data["results"]}
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert assignee_ids == {str(support_a.id), str(support_b.id)}

    def test_manager_filter_tickets_by_one_support(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        TicketFactory.create_batch(2, assignee=support_a)
        tickets_of_b = TicketFactory.create_batch(3, assignee=support_b)

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/?assignee={support_b.id}")

        returned_ids = {item["id"] for item in response.data["results"]}
        assert returned_ids == {str(ticket.id) for ticket in tickets_of_b}

    def test_filter_tickets_by_current_status(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        new_ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=new_ticket, status=TicketHistory.Status.NEW)
        processing_ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=processing_ticket, status=TicketHistory.Status.NEW)
        TicketHistoryFactory(
            ticket=processing_ticket, status=TicketHistory.Status.PROCESSING
        )
        closed_ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=closed_ticket, status=TicketHistory.Status.NEW)
        TicketHistoryFactory(
            ticket=closed_ticket, status=TicketHistory.Status.PROCESSING
        )
        TicketHistoryFactory(ticket=closed_ticket, status=TicketHistory.Status.SOLVED)
        TicketHistoryFactory(ticket=closed_ticket, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=requester)
        response = api_client.get("/api/v1/tickets/?status=PROCESSING")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(processing_ticket.id)]

    def test_order_tickets_by_priority_severity(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        low = TicketFactory(priority="LOW")
        urgent = TicketFactory(priority="URGENT")
        medium = TicketFactory(priority="MEDIUM")
        high = TicketFactory(priority="HIGH")

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/?ordering=-priority")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [
            str(urgent.id),
            str(high.id),
            str(medium.id),
            str(low.id),
        ]


class TestTicketQueue:
    def test_queue_sorted_by_priority_then_oldest_first(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        td_30 = TicketFactory(priority="MEDIUM")
        td_31 = TicketFactory(priority="URGENT")
        td_32 = TicketFactory(priority="MEDIUM")
        for ticket, hour in ((td_30, 8), (td_31, 9), (td_32, 7)):
            TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
            Ticket.objects.filter(pk=ticket.pk).update(
                created_at=timezone.now().replace(hour=hour, minute=0)
                - timedelta(days=1)
            )

        api_client.force_authenticate(user=support)
        response = api_client.get("/api/v1/tickets/queue/")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert response.status_code == status.HTTP_200_OK
        assert returned_ids == [str(td_31.id), str(td_32.id), str(td_30.id)]

    def test_queue_only_contains_unassigned_new_tickets(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        waiting = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=waiting, status=TicketHistory.Status.NEW)
        claimed = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=claimed, status=TicketHistory.Status.NEW)
        TicketHistoryFactory(ticket=claimed, status=TicketHistory.Status.PROCESSING)
        cancelled = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=cancelled, status=TicketHistory.Status.NEW)
        TicketHistoryFactory(ticket=cancelled, status=TicketHistory.Status.CANCELLED)

        api_client.force_authenticate(user=support)
        response = api_client.get("/api/v1/tickets/queue/")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(waiting.id)]

    def test_filter_queue_by_category(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        network = CategoryFactory(name="Phần cứng/Mạng")
        software = CategoryFactory(name="Phần mềm")
        network_ticket = TicketFactory(category=network)
        TicketHistoryFactory(ticket=network_ticket, status=TicketHistory.Status.NEW)
        software_ticket = TicketFactory(category=software)
        TicketHistoryFactory(ticket=software_ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/queue/?category={network.id}")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(network_ticket.id)]

    def test_overdue_ticket_in_queue_is_flagged(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/queue/")

        assert response.data["results"][0]["is_overdue"] is True

    def test_requester_cannot_access_queue(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=requester)
        response = api_client.get("/api/v1/tickets/queue/")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestHandledTicketHistory:
    def test_support_sees_own_solved_closed_and_rejected_tickets(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        handled_ids = set()
        for final_status in (
            TicketHistory.Status.SOLVED,
            TicketHistory.Status.CLOSED,
            TicketHistory.Status.REJECTED,
        ):
            ticket = TicketFactory(assignee=support)
            TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
            TicketHistoryFactory(ticket=ticket, status=final_status)
            handled_ids.add(str(ticket.id))
        in_progress = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=in_progress, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        response = api_client.get("/api/v1/tickets/handled/")

        returned_ids = {item["id"] for item in response.data["results"]}
        assert response.status_code == status.HTTP_200_OK
        assert returned_ids == handled_ids

    def test_support_does_not_see_tickets_handled_by_others(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket_of_b = TicketFactory(assignee=support_b)
        TicketHistoryFactory(ticket=ticket_of_b, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=support_a)
        response = api_client.get("/api/v1/tickets/handled/")

        assert response.data["count"] == 0

    def test_support_cannot_see_team_history_with_assignee_param(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        own_ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=own_ticket, status=TicketHistory.Status.CLOSED)
        ticket_of_b = TicketFactory(assignee=support_b)
        TicketHistoryFactory(ticket=ticket_of_b, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=support_a)
        response = api_client.get(f"/api/v1/tickets/handled/?assignee={support_b.id}")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(own_ticket.id)]

    def test_manager_sees_handled_tickets_of_whole_team(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        for support in (support_a, support_b):
            ticket = TicketFactory(assignee=support)
            TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/handled/")

        assignee_ids = {item["assignee"]["id"] for item in response.data["results"]}
        assert assignee_ids == {str(support_a.id), str(support_b.id)}
        assert all(item["resolved_at"] for item in response.data["results"])

    def test_manager_filter_handled_tickets_by_one_support(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket_of_a = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket_of_a, status=TicketHistory.Status.CLOSED)
        ticket_of_b = TicketFactory(assignee=support_b)
        TicketHistoryFactory(ticket=ticket_of_b, status=TicketHistory.Status.CLOSED)

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/handled/?assignee={support_b.id}")

        returned_ids = [item["id"] for item in response.data["results"]]
        assert returned_ids == [str(ticket_of_b.id)]

    def test_ticket_resolved_after_sla_is_marked_resolved_late(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        late_ticket = TicketFactory(assignee=support, priority="HIGH")
        TicketHistoryFactory(ticket=late_ticket, status=TicketHistory.Status.SOLVED)
        Ticket.objects.filter(pk=late_ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=30)
        )
        on_time_ticket = TicketFactory(assignee=support, priority="HIGH")
        TicketHistoryFactory(ticket=on_time_ticket, status=TicketHistory.Status.SOLVED)

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/handled/")

        late_flags = {
            item["id"]: item["is_resolved_late"] for item in response.data["results"]
        }
        assert late_flags[str(late_ticket.id)] is True
        assert late_flags[str(on_time_ticket.id)] is False

    def test_requester_cannot_access_handled_history(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=requester)
        response = api_client.get("/api/v1/tickets/handled/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
