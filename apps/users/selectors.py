from django.db.models import OuterRef, Q, Subquery

from apps.tickets.models import TicketHistory
from apps.tickets.selectors import tickets_with_current_status
from apps.users.models import User


def get_it_supports(is_active=None, available=None, search=None):
    processing = (
        tickets_with_current_status()
        .filter(assignee=OuterRef("pk"), current_status=TicketHistory.Status.PROCESSING)
        .order_by("created_at")
    )

    qs = (
        User.objects.filter(role=User.Role.IT_SUPPORT)
        .annotate(
            current_ticket_id=Subquery(processing.values("pk")[:1]),
            current_ticket_title=Subquery(processing.values("title")[:1]),
        )
        .order_by("username")
    )

    if is_active is not None:
        qs = qs.filter(is_active=is_active)

    if available is True:
        qs = qs.filter(current_ticket_id__isnull=True)
    elif available is False:
        qs = qs.filter(current_ticket_id__isnull=False)

    if search:
        qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))

    return qs
