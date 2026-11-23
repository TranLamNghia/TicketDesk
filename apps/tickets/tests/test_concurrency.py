import threading

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.tickets.models import TicketHistory
from apps.tickets.services import claim_ticket
from apps.tickets.tests.factories import (
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User

# transaction=True: data is really committed, so the threads (each with its own
# database connection) can see it. select_for_update only works on PostgreSQL.
pytestmark = pytest.mark.django_db(transaction=True)


class TestClaimTicketRaceCondition:
    def test_two_supports_claiming_same_ticket_only_one_succeeds(self):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        start_together = threading.Barrier(2)
        successes = []
        errors = []

        def claim(support):
            try:
                start_together.wait()
                claim_ticket(ticket.id, support)
                successes.append(support)
            except ValidationError as ex:
                errors.append(ex)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=claim, args=(support_a,)),
            threading.Thread(target=claim, args=(support_b,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        ticket.refresh_from_db()
        assert len(successes) == 1
        assert len(errors) == 1
        assert "Ticket has been assigned." in errors[0].messages
        assert ticket.assignee == successes[0]
        assert (
            ticket.status_history.filter(status=TicketHistory.Status.PROCESSING).count()
            == 1
        )
