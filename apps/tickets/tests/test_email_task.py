import pytest
from django.core import mail
from apps.tickets.services import TicketHistory
from apps.tickets.services import (
    claim_ticket,
    assign_ticket,
    create_comment,
)
from apps.tickets.tests.factories import (
    TicketFactory,
    UserFactory,
    TicketHistoryFactory,
)
from apps.users.models import User


@pytest.mark.django_db(transaction=True)
def test_claim_ticket_sends_status_notification_email():
    requester = UserFactory(role=User.Role.REQUESTER, email="requester@rainscales.com")
    support = UserFactory(role=User.Role.IT_SUPPORT, email="support@rainscales.com")
    ticket = TicketFactory(created_by=requester, assignee=None)
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
    claim_ticket(ticket.pk, support_user=support)

    assert len(mail.outbox) >= 1
    sent_email = mail.outbox[-1]
    assert requester.email in sent_email.to
    assert "Ticket #" in sent_email.subject
    assert "PROCESSING" in sent_email.body


@pytest.mark.django_db(transaction=True)
def test_assign_ticket_sends_assigned_notification_email():
    manager = UserFactory(role=User.Role.IT_MANAGER)
    support = UserFactory(role=User.Role.IT_SUPPORT, email="support01@rainscales.com")
    ticket = TicketFactory(assignee=None)
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

    assign_ticket(ticket.pk, support_user=support, assigned_by=manager)

    assert len(mail.outbox) >= 1
    sent_email = mail.outbox[-1]
    assert support.email in sent_email.to
    assert "Bạn được phân công xử lý ticket" in sent_email.subject


@pytest.mark.django_db(transaction=True)
def test_create_comment_sends_email_to_counterpart():
    requester = UserFactory(role=User.Role.REQUESTER, email="requester@rainscales.com")
    support = UserFactory(role=User.Role.IT_SUPPORT, email="support@rainscales.com")
    ticket = TicketFactory(created_by=requester, assignee=support)
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

    create_comment(
        ticket=ticket, author=requester, content="Tôi cập nhật thêm ảnh lỗi."
    )

    assert len(mail.outbox) >= 1
    sent_email = mail.outbox[-1]
    assert support.email in sent_email.to
    assert "Có phản hồi mới" in sent_email.subject
