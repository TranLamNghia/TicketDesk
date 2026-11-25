from celery import shared_task
from apps.tickets.services import (
    auto_close_solved_tickets,
)
from pathlib import Path
from apps.tickets.models import Ticket
from apps.tickets.services import export_tickets_to_excel
from apps.users.models import User
from apps.notifications.tasks import send_ticket_notification_email


@shared_task
def auto_close_solved_tickets_task() -> int:
    count = auto_close_solved_tickets()

    return count


@shared_task(bind=True)
def export_tickets_excel_task(self, user_id: str = None) -> str:
    queryset = (
        Ticket.objects.select_related("category", "created_by", "assignee")
        .prefetch_related("status_history")
        .order_by("-created_at")
    )
    file_path = export_tickets_to_excel(queryset)

    if user_id:
        try:
            user = User.objects.get(pk=user_id)
            if user.email:
                filename = Path(file_path).name
                send_ticket_notification_email.delay(
                    recipient_email=user.email,
                    subject="[TicketDesk] Báo cáo danh sách Ticket đã sẵn sàng",
                    message=(
                        f"Xin chào {user.username},\n\n"
                        f"Yêu cầu xuất báo cáo danh sách Ticket của bạn đã hoàn tất.\n"
                        f"File báo cáo: {filename}\n"
                    ),
                )
        except User.DoesNotExist:
            pass

    return file_path
