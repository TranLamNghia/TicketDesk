import django_filters
from rest_framework.filters import OrderingFilter

from apps.tickets.models import Ticket, TicketHistory
from apps.tickets.selectors import PRIORITY_RANK, filter_by_current_status


class TicketFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=TicketHistory.Status.choices, method="filter_by_status"
    )

    created_by_username = django_filters.CharFilter(
        field_name="created_by__username", lookup_expr="iexact"
    )

    class Meta:
        model = Ticket
        fields = {
            "priority": ["exact"],
            "category": ["exact"],
            "created_by": ["exact"],
            "assignee": ["exact"],
            "created_at": ["gte", "lte"],
        }

    def filter_by_status(self, queryset, name, value):
        if not value:
            return queryset

        # US07 KB3: filter on the CURRENT status, not on any past status
        return filter_by_current_status(queryset, [value])


class TicketOrderingFilter(OrderingFilter):
    """
    `?ordering=priority` sorts by severity (LOW < MEDIUM < HIGH < URGENT)
    instead of alphabetically. Use `?ordering=-priority` for URGENT first.
    """

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset

        if any(field.lstrip("-") == "priority" for field in ordering):
            queryset = queryset.annotate(priority_rank=PRIORITY_RANK)
            ordering = [
                field.replace("priority", "priority_rank")
                if field.lstrip("-") == "priority"
                else field
                for field in ordering
            ]

        return queryset.order_by(*ordering)
