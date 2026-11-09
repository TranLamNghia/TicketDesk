from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="list"),
    path("new/", views.TicketCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.TicketDetailView.as_view(), name="detail"),
    path("stats/", views.TicketStatsView.as_view(), name="stats"),
]
