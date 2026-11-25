import os
import openpyxl
import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import TicketHistory
from apps.tickets.services import export_tickets_to_excel
from apps.tickets.tasks import export_tickets_excel_task
from apps.tickets.tests.factories import (
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User


@pytest.mark.django_db
def test_export_tickets_to_excel_creates_valid_file(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    requester = UserFactory(username="requester01")
    support = UserFactory(username="support01")
    ticket = TicketFactory(
        title="Test Ticket Export", created_by=requester, assignee=support
    )
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

    file_path = export_tickets_to_excel([ticket])

    assert os.path.exists(file_path)
    wb = openpyxl.load_workbook(file_path)
    assert "Ticket Report" in wb.sheetnames
    ws = wb["Ticket Report"]

    assert ws.cell(row=1, column=1).value == "Mã ticket"
    assert ws.cell(row=2, column=2).value == "Test Ticket Export"
    assert ws.cell(row=2, column=5).value == "PROCESSING"


@pytest.mark.django_db
def test_export_tickets_excel_task_runs_and_notifies_user(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    manager = UserFactory(role=User.Role.IT_MANAGER, email="manager@rainscales.com")
    ticket = TicketFactory()
    TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)
    result = export_tickets_excel_task.delay(user_id=str(manager.pk))

    assert result.successful()
    assert os.path.exists(result.result)
    assert len(mail.outbox) >= 1

    sent_email = mail.outbox[-1]

    assert manager.email in sent_email.to
    assert "Báo cáo danh sách Ticket đã sẵn sàng" in sent_email.subject


@pytest.mark.django_db
def test_export_excel_api_permissions():
    client = APIClient()
    manager = UserFactory(role=User.Role.IT_MANAGER)
    requester = UserFactory(role=User.Role.REQUESTER)

    client.force_authenticate(user=manager)
    res_mgr = client.get("/api/v1/tickets/export-excel/")

    assert res_mgr.status_code == status.HTTP_200_OK
    assert ".xlsx" in res_mgr["Content-Disposition"]

    client.force_authenticate(user=requester)
    res_req = client.get("/api/v1/tickets/export-excel/")

    assert res_req.status_code == status.HTTP_403_FORBIDDEN
