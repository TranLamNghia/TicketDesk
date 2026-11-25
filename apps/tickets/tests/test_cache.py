import pytest
from django.core.cache import cache

from apps.tickets.models import TicketHistory
from apps.tickets.selectors import (
    OVERVIEW_KPIS_CACHE_KEY,
    get_overview_kpis,
)
from apps.tickets.services import claim_ticket
from apps.tickets.tests.factories import (
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User


@pytest.mark.django_db
def test_get_overview_kpis_uses_cache_on_second_call(django_assert_num_queries):
    cache.clear()
    TicketFactory()

    kpis_first = get_overview_kpis(use_cache=True)
    assert kpis_first["total_tickets"] == 1
    assert cache.get(OVERVIEW_KPIS_CACHE_KEY) is not None

    with django_assert_num_queries(0):
        kpis_second = get_overview_kpis(use_cache=True)
    assert kpis_second == kpis_first


@pytest.mark.django_db(transaction=True)
def test_changing_ticket_status_invalidates_kpis_cache():
    cache.clear()
    support = UserFactory(role=User.Role.IT_SUPPORT)
    ticket = TicketFactory(assignee=None)
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

    get_overview_kpis(use_cache=True)
    assert cache.get(OVERVIEW_KPIS_CACHE_KEY) is not None

    claim_ticket(ticket.pk, support_user=support)

    assert cache.get(OVERVIEW_KPIS_CACHE_KEY) is None
