from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from apps.users.models import User
from .models import Ticket


class TicketQuerysetMixin:
    def get_queryset(self):
        qs = Ticket.objects.select_related("category", "assignee", "created_by")
        if self.request.user.role == User.Role.REQUESTER:
            qs = qs.filter(created_by=self.request.user)
        return qs


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
