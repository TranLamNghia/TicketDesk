from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from apps.tickets.models import Ticket, Comment
from apps.users.models import User
from apps.tickets.selectors import (
    get_current_status,
)


from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rainscales.com")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_notification_email(
    self, recipient_email: str, subject: str, message: str
):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient_email],
        )

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_status_changed_email(self, ticket_id: str):
    try:
        ticket = Ticket.objects.select_related("created_by").get(pk=ticket_id)
        current_status = get_current_status(ticket)

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rainscales.com")
        subject = f"[TicketDesk] Ticket #{ticket.pk} vừa được cập nhật trạng thái"
        message = (
            f"Xin chào {ticket.created_by.username},\n\n"
            f"Ticket đã chuyển sang trạng thái {current_status}\n"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[ticket.created_by.email],
        )

    except Ticket.DoesNotExist:
        return
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_ticket_assigned_email(
    self, ticket_id: str, assignee_id: str, reason: str = ""
):
    try:
        ticket = Ticket.objects.get(pk=ticket_id)
        assignee = User.objects.get(pk=assignee_id)

        if not assignee.email:
            return

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rainscales.com")
        subject = f"[TicketDesk] Bạn được phân công xử lý ticket #{ticket.pk}"
        message = (
            f"Xin chào {assignee.username},\n\n"
            f"Bạn vừa được phân công xử lý ticket: {ticket.title}\n"
            f"Độ ưu tiên: {ticket.priority}\n"
        )

        if reason:
            message += f"Lý do phân công/bàn giao: {reason}\n"
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[assignee.email],
        )

    except (Ticket.DoesNotExist, User.DoesNotExist):
        return
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_comment_notification_email(self, comment_id: str):
    try:
        comment = Comment.objects.select_related(
            "ticket", "author", "ticket__created_by", "ticket__assignee"
        ).get(pk=comment_id)
        ticket = comment.ticket

        recipient = None

        if comment.author == ticket.created_by:
            recipient = ticket.assignee
        else:
            recipient = ticket.created_by

        if not recipient or not recipient.email:
            return

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rainscales.com")
        subject = f"[TicketDesk] Có phản hồi mới trên ticket #{ticket.pk}"
        message = (
            f"Xin chào {recipient.username},\n\n"
            f"{comment.author.username} vừa bình luận trên ticket '{ticket.title}':\n\n"
            f'"{comment.content}"\n'
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient.email],
        )

    except Comment.DoesNotExist:
        return
    except Exception as exc:
        raise self.retry(exc=exc)
