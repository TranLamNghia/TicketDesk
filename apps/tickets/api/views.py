from rest_framework import viewsets, permissions
from django.db import transaction

from apps.tickets.models import Category, Ticket, TicketHistory
from apps.tickets.api.serializers import (
    CategorySerializer,
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCreateSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Ticket.objects.select_related("category", "created_by", "assignee")

        if self.action == "retrieve":
            return qs.prefetch_related(
                "status_history",
                "comments__author",
            )

        return qs.prefetch_related("status_history")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TicketDetailSerializer
        elif self.action == "create":
            return TicketCreateSerializer

        return TicketListSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            ticket = serializer.save(created_by=self.request.user)
            TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.NEW)
