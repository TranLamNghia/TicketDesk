from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from apps.users.models import User

from apps.tickets.models import Category, Ticket, TicketHistory
from apps.tickets.api.serializers import (
    CategorySerializer,
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCreateSerializer,
)
from apps.tickets.api.permissions import (
    IsManagerOrReadOnly,
    IsTicketAccessAllowed,
)
from apps.tickets.api.filters import TicketFilter


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name"]


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTicketAccessAllowed]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TicketFilter
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "priority"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related("category", "created_by", "assignee")

        if user.is_authenticated and user.role == User.Role.REQUESTER:
            qs = qs.filter(created_by=user)

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
