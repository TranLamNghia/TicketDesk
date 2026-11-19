from datetime import timedelta

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
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


class TestSlaDeadline:
    @pytest.mark.parametrize(
        ("priority", "hours"),
        [("URGENT", 8), ("HIGH", 24), ("MEDIUM", 48), ("LOW", 72)],
    )
    def test_sla_due_at_depends_on_priority(self, api_client, priority, hours):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority=priority)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert parse_datetime(response.data["sla_due_at"]) == (
            ticket.created_at + timedelta(hours=hours)
        )

    def test_changing_priority_recalculates_sla_due_at(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, priority="LOW")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=manager)
        api_client.patch(f"/api/v1/tickets/{ticket.id}/", {"priority": "URGENT"})
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.data["priority"] == "URGENT"
        assert parse_datetime(response.data["sla_due_at"]) == (
            ticket.created_at + timedelta(hours=8)
        )


class TestOverdueFlag:
    def test_high_ticket_waiting_more_than_24_hours_is_overdue(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )

        api_client.force_authenticate(user=manager)
        response = api_client.get("/api/v1/tickets/")

        result = next(
            item for item in response.data["results"] if item["id"] == str(ticket.id)
        )
        assert result["is_overdue"] is True

    def test_ticket_within_sla_is_not_overdue(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=5)
        )

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.data["is_overdue"] is False

    def test_processing_ticket_past_sla_is_overdue(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, priority="URGENT")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(hours=9)
        )

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.data["is_overdue"] is True

    def test_reopened_ticket_is_never_overdue(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support, priority="HIGH")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.REOPEN)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        api_client.force_authenticate(user=support)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.data["status"] == TicketHistory.Status.REOPEN
        assert response.data["is_overdue"] is False

    def test_finished_ticket_is_not_overdue(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory(priority="URGENT")
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)
        Ticket.objects.filter(pk=ticket.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        api_client.force_authenticate(user=manager)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert response.data["is_overdue"] is False
