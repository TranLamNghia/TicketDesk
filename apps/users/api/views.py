from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tickets.api.exceptions import SERVICE_EXCEPTIONS, to_api_exception
from apps.tickets.api.permissions import IsManager, IsSupportOrManager
from apps.users.api.serializers import (
    ChangePasswordSerializer,
    GrantITSupportSerializer,
    ITSupportSerializer,
    ITSupportUpdateSerializer,
    RegisteredUserSerializer,
    RegisterSerializer,
)
from apps.users.selectors import get_it_supports
from apps.users.services import (
    change_password,
    deactivate_it_support,
    grant_it_support_role,
    register_requester,
)


def _parse_bool(value):
    if value is None:
        return None
    value = value.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return None


class ITSupportViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ITSupportSerializer
    filter_backends = []
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated(), IsSupportOrManager()]

        return [permissions.IsAuthenticated(), IsManager()]

    def get_queryset(self):
        params = self.request.query_params
        return get_it_supports(
            is_active=_parse_bool(params.get("is_active")),
            available=_parse_bool(params.get("available")),
            search=(params.get("search") or "").strip() or None,
        )

    def _support_response(self, user_id, status_code=status.HTTP_200_OK):
        support = get_it_supports().get(pk=user_id)

        return Response(ITSupportSerializer(support).data, status=status_code)

    def create(self, request):
        serializer = GrantITSupportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = grant_it_support_role(serializer.validated_data["user_id"])
        except ObjectDoesNotExist:
            return Response(
                {"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        return self._support_response(user.pk, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        support = self.get_object()
        serializer = ITSupportUpdateSerializer(support, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return self._support_response(support.pk)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        support = self.get_object()
        try:
            deactivate_it_support(support.pk)
        except SERVICE_EXCEPTIONS as ex:
            raise to_api_exception(ex)

        return self._support_response(support.pk)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = register_requester(
                username=data["username"],
                email=data["email"],
                password=data["password"],
            )
        except DjangoValidationError as ex:
            return Response({"email": ex.messages}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            RegisteredUserSerializer(user).data, status=status.HTTP_201_CREATED
        )


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        change_password(request.user, serializer.validated_data["new_password"])

        return Response(
            {"detail": "Password changed successfully."}, status=status.HTTP_200_OK
        )
