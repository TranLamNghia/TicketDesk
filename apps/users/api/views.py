from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tickets.api.permissions import IsSupportOrManager
from apps.users.api.serializers import (
    ChangePasswordSerializer,
    ITSupportSerializer,
    RegisteredUserSerializer,
    RegisterSerializer,
)
from apps.users.selectors import get_it_supports
from apps.users.services import change_password, register_requester


def _parse_bool(value):
    if value is None:
        return None
    value = value.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return None


class ITSupportViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ITSupportSerializer
    permission_classes = [permissions.IsAuthenticated, IsSupportOrManager]
    filter_backends = []

    def get_queryset(self):
        params = self.request.query_params
        return get_it_supports(
            is_active=_parse_bool(params.get("is_active")),
            available=_parse_bool(params.get("available")),
            search=(params.get("search") or "").strip() or None,
        )


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
