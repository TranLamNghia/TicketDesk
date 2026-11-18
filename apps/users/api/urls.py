from rest_framework.routers import DefaultRouter
from apps.users.api.views import ITSupportViewSet

router = DefaultRouter()
router.register(r"it-supports", ITSupportViewSet, basename="it-support")

urlpatterns = router.urls
