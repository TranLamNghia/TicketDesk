from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from django.db.models import Prefetch

from .models import Ticket, TicketHistory
from .selectors import (
    count_solved_ticket_per_IT_Support,
    count_ticket_by_status,
    get_overview_kpis,
)


class TicketQuerysetMixin:
    def get_queryset(self):
        return Ticket.objects.select_related(
            "category", "created_by", "assignee"
        ).prefetch_related(
            Prefetch(
                "status_history",
                queryset=TicketHistory.objects.order_by("-update_status_at"),
            )
        )


class TicketListView(LoginRequiredMixin, TicketQuerysetMixin, ListView):
    model = Ticket
    paginate_by = 20
    context_object_name = "tickets"
    template_name = "tickets/ticket_list.html"


class TicketDetailView(LoginRequiredMixin, TicketQuerysetMixin, DetailView):
    model = Ticket
    context_object_name = "ticket"
    template_name = "tickets/ticket_detail.html"


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    fields = ["title", "description", "category", "priority"]
    template_name = "tickets/ticket_form.html"
    success_url = reverse_lazy("tickets:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TicketStatsView(LoginRequiredMixin, TemplateView):
    def get_context_data(seft, **kwargs):
        context = super().get_context_data(**kwargs)
        context["kpis"] = get_overview_kpis()
        context["status_stats"] = count_ticket_by_status()
        context["support_stats"] = count_solved_ticket_per_IT_Support()

        return context
