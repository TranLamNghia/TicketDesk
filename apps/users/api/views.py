from rest_framework import permissions, viewsets

from apps.tickets.api.permissions import IsSupportOrManager
from apps.users.api.serializers import ITSupportSerializer
from apps.users.selectors import get_it_supports


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
