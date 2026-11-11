from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from apps.tickets.services import claim_ticket, reassign_ticket, assign_ticket
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from apps.users.models import User
from apps.tickets.models import Category, Ticket, TicketHistory, Comment
from apps.tickets.api.serializers import (
    CategorySerializer,
    TicketListSerializer,
    TicketDetailSerializer,
    TicketCreateSerializer,
    CommentSerializer,
)
from apps.tickets.api.permissions import (
    IsManagerOrReadOnly,
    IsTicketAccessAllowed,
    IsManager,
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

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        user = request.user

        if user.role != User.Role.IT_SUPPORT and not user.is_superuser:
            return Response(
                {"detail": "Only IT Support can claim ticket."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ticket = self.get_object()
        try:
            ticket = claim_ticket(ticket.id, user)
        except (ValidationError, ValueError) as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsManager],
    )
    def assign(self, request, pk=None):
        ticket = self.get_object()
        support_id = request.data.get("support_id")
        if not support_id:
            return Response(
                {"support_id": ["This feild is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            support_user = User.objects.get(id=support_id, role=User.Role.IT_SUPPORT)
        except User.DoesNotExist:
            return Response(
                {"support_id": ["IT Support not found."]},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            ticket = assign_ticket(ticket.id, support_user, request.user)
        except (ValidationError, ValueError) as ex:
            return Response(
                {"detail": getattr(ex, "message", str(ex))},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsManager],
    )
    def reassign(self, request, pk=None):
        ticket = self.get_object()
        received_by_id = request.data.get("received_by")
        reason = request.data.get("reason", "").strip()

        if not received_by_id:
            return Response(
                {"received_by": ["This feild is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            received_by = User.objects.get(id=received_by_id, role=User.Role.IT_SUPPORT)
        except User.DoesNotExist:
            return Response(
                {"received_by": ["IT Support not found."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ticket = reassign_ticket(ticket.id, request.user, received_by, reason)
        except (ValidationError, ValueError) as ex:
            return Response({"detail": str(ex)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Comment.objects.select_related("author", "ticket")
        ticket_id = self.request.query_params.get("ticket")

        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
