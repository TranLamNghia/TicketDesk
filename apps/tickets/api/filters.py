import django_filters
from apps.tickets.models import Ticket, TicketHistory


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

        return queryset.filter(status_history__status=value).distinct()
