from rest_framework.routers import DefaultRouter
from apps.tickets.api.views import CategoryViewSet, TicketViewSet, CommentViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"tickets", TicketViewSet, basename="ticket")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = router.urls
