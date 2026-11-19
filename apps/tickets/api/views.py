from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.tickets.services import (
    claim_ticket,
    reassign_ticket,
    assign_ticket,
    solve_ticket,
    reject_ticket,
    close_ticket,
    reopen_ticket,
    resume_ticket,
    cancel_ticket,
    create_comment,
    validate_ticket_update,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from apps.users.models import User
from apps.tickets.models import (
    Category,
    Ticket,
    TicketHistory,
    Comment,
    AttachmentTicket,
)
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
    IsSupport,
    IsSupportOrManager,
    IsRequester,
)
from apps.tickets.api.exceptions import SERVICE_EXCEPTIONS, to_api_exception
from apps.tickets.api.filters import TicketFilter
from apps.tickets.api.throttles import enforce_ticket_creation_quota


def _get_active_support(user_id):
    """Only active IT Support accounts can receive a ticket."""
    if not user_id:
        return None
    try:
        return User.objects.get(id=user_id, role=User.Role.IT_SUPPORT, is_active=True)
    except (User.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        return None


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsManagerOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name"]


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTicketAccessAllowed]

    parser_classes = [JSONParser, MultiPartParser, FormParser]
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
                "comments__attachments",
                "attachments",
            )

        return qs.prefetch_related("status_history")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TicketDetailSerializer
        elif self.action in ("create", "update", "partial_update"):
            return TicketCreateSerializer

        return TicketListSerializer

    def create(self, request, *args, **kwargs):
        enforce_ticket_creation_quota(request.user)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        attachment_file = serializer.validated_data.pop("attachment", None)

        with transaction.atomic():
            ticket = serializer.save(created_by=self.request.user)
            TicketHistory.objects.create(ticket=ticket, status=TicketHistory.Status.NEW)

            if attachment_file:
                AttachmentTicket.objects.create(
                    ticket=ticket, url=attachment_file, size=attachment_file.size
                )

    def update(self, request, *args, **kwargs):
        ticket = self.get_object()
        try:
            validate_ticket_update(ticket, request.user, request.data.keys())
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        return super().update(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsSupport],
    )
    def claim(self, request, pk=None):
        ticket = self.get_object()
        try:
            ticket = claim_ticket(ticket.id, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

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

        support_user = _get_active_support(support_id)
        if support_user is None:
            return Response(
                {"support_id": ["IT Support not found or inactive."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ticket = assign_ticket(ticket.id, support_user, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsSupportOrManager],
    )
    def reassign(self, request, pk=None):
        ticket = self.get_object()
        received_by_id = request.data.get("received_by") or request.data.get(
            "assignee_id"
        )
        reason = (request.data.get("reason") or "").strip()

        if not received_by_id:
            return Response(
                {"received_by": ["This feild is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reason:
            return Response(
                {"reason": ["Please enter a reason for transferring the ticket."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        received_by = _get_active_support(received_by_id)
        if received_by is None:
            return Response(
                {"received_by": ["IT Support not found or inactive."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ticket = reassign_ticket(ticket.id, request.user, received_by, reason)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsSupport],
    )
    def solve(self, request, pk=None):
        ticket = self.get_object()

        try:
            ticket = solve_ticket(ticket.id, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsSupport],
    )
    def resume(self, request, pk=None):
        # US15 KB4: the assigned IT Support continues a REOPEN ticket
        # (REOPEN -> PROCESSING) when they choose to.
        ticket = self.get_object()

        try:
            ticket = resume_ticket(ticket.id, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsSupportOrManager],
    )
    def reject(self, request, pk=None):
        ticket = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response(
                {"reason": ["A reason for refusal is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ticket = reject_ticket(ticket.id, request.user, reason)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsRequester],
    )
    def close(self, request, pk=None):
        ticket = self.get_object()

        try:
            ticket = close_ticket(ticket.id, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsRequester],
    )
    def reopen(self, request, pk=None):
        ticket = self.get_object()
        reason = (request.data.get("reason") or "").strip()

        if not reason:
            return Response(
                {"reason": ["A reason for reopen is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ticket = reopen_ticket(ticket.id, request.user, reason)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsRequester],
    )
    def cancel(self, request, pk=None):
        ticket = self.get_object()

        try:
            ticket = cancel_ticket(ticket.id, request.user)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer = self.get_serializer(ticket)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Comment.objects.select_related("author", "ticket").prefetch_related(
            "attachments"
        )

        # Same visibility rule as TicketViewSet: a Requester only sees
        # comments of tickets they created.
        user = self.request.user
        if user.role == User.Role.REQUESTER:
            qs = qs.filter(ticket__created_by=user)

        ticket_id = self.request.query_params.get("ticket")

        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)

        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        try:
            comment = create_comment(
                ticket=data["ticket"],
                author=self.request.user,
                content=data["content"],
                attachment=data.get("attachment"),
            )
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        serializer.instance = comment
