from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView

from apps.users.api.views import ChangePasswordView, ITSupportViewSet, RegisterView

router = DefaultRouter()
router.register(r"it-supports", ITSupportViewSet, basename="it-support")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/logout/", TokenBlacklistView.as_view(), name="auth_logout"),
    path(
        "auth/password/change/",
        ChangePasswordView.as_view(),
        name="auth_password_change",
    ),
    *router.urls,
]
