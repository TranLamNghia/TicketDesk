from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.users.models import User


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == User.Role.IT_MANAGER or request.user.is_superuser)
        )


class IsManagerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == User.Role.IT_MANAGER or request.user.is_superuser)
        )


class IsTicketAccessAllowed(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.is_superuser or user.role == User.Role.IT_MANAGER:
            return True

        if user.role == User.Role.IT_SUPPORT:
            if request.method in SAFE_METHODS:
                return True

            return obj.assignee == user or obj.assignee is None

        return obj.created_by == user
