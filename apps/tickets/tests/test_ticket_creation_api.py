from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import AttachmentTicket, Ticket
from apps.tickets.tests.factories import (
    CategoryFactory,
    TicketFactory,
    UserFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestTicketAttachmentValidation:
    def test_create_ticket_with_image_attachment_success(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        image = SimpleUploadedFile("loi.png", b"x" * 1024, content_type="image/png")

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy tính không vào được mạng",
            "description": "Cắm dây mạng nhưng biểu tượng mạng vẫn báo lỗi.",
            "priority": "HIGH",
            "category": str(category.id),
            "attachment": image,
        }

        response = api_client.post("/api/v1/tickets/", payload, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert AttachmentTicket.objects.filter(ticket_id=response.data["id"]).exists()

    def test_create_ticket_with_non_image_attachment_fails(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        text_file = SimpleUploadedFile("log.txt", b"error log")

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy tính không vào được mạng",
            "description": "Cắm dây mạng nhưng biểu tượng mạng vẫn báo lỗi.",
            "priority": "HIGH",
            "category": str(category.id),
            "attachment": text_file,
        }

        response = api_client.post("/api/v1/tickets/", payload, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "attachment" in response.data
        assert not Ticket.objects.filter(created_by=requester).exists()

    def test_create_ticket_with_attachment_over_5mb_fails(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        big_image = SimpleUploadedFile("loi.png", b"x" * (6 * 1024 * 1024))

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy tính không vào được mạng",
            "description": "Cắm dây mạng nhưng biểu tượng mạng vẫn báo lỗi.",
            "priority": "HIGH",
            "category": str(category.id),
            "attachment": big_image,
        }

        response = api_client.post("/api/v1/tickets/", payload, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "attachment" in response.data
        assert not Ticket.objects.filter(created_by=requester).exists()


class TestTicketRequiredFields:
    def test_create_ticket_without_category_fails(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy in bị kẹt giấy",
            "description": "Kẹt giấy ở khay số 2.",
            "priority": "LOW",
        }

        response = api_client.post("/api/v1/tickets/", payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.data
        assert not Ticket.objects.filter(created_by=requester).exists()


class TestTicketCreationRateLimit:
    def test_requester_cannot_create_more_than_5_tickets_per_hour(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()

        api_client.force_authenticate(user=requester)
        for index in range(5):
            payload = {
                "title": f"Sự cố mạng số {index}",
                "description": "Mạng chập chờn liên tục.",
                "priority": "MEDIUM",
                "category": str(category.id),
            }
            response = api_client.post("/api/v1/tickets/", payload, format="json")
            assert response.status_code == status.HTTP_201_CREATED

        payload = {
            "title": "Sự cố mạng số 6",
            "description": "Mạng chập chờn liên tục.",
            "priority": "MEDIUM",
            "category": str(category.id),
        }
        response = api_client.post("/api/v1/tickets/", payload, format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "5 tickets per hour" in response.data["detail"]
        assert "Retry-After" in response
        assert Ticket.objects.filter(created_by=requester).count() == 5

    def test_tickets_older_than_1_hour_do_not_count_toward_hourly_limit(
        self, api_client
    ):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        TicketFactory.create_batch(5, created_by=requester)
        Ticket.objects.filter(created_by=requester).update(
            created_at=timezone.now() - timedelta(hours=2)
        )

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy chiếu phòng họp không lên hình",
            "description": "Đã thử đổi cáp HDMI nhưng vẫn không có tín hiệu.",
            "priority": "HIGH",
            "category": str(category.id),
        }

        response = api_client.post("/api/v1/tickets/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_requester_cannot_create_more_than_20_tickets_per_day(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        TicketFactory.create_batch(20, created_by=requester)
        Ticket.objects.filter(created_by=requester).update(
            created_at=timezone.now() - timedelta(hours=3)
        )

        api_client.force_authenticate(user=requester)
        payload = {
            "title": "Máy chiếu phòng họp không lên hình",
            "description": "Đã thử đổi cáp HDMI nhưng vẫn không có tín hiệu.",
            "priority": "HIGH",
            "category": str(category.id),
        }

        response = api_client.post("/api/v1/tickets/", payload, format="json")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "20 tickets per day" in response.data["detail"]

    def test_rate_limit_does_not_affect_other_requesters(self, api_client):
        requester_1 = UserFactory(role=User.Role.REQUESTER)
        requester_2 = UserFactory(role=User.Role.REQUESTER)
        category = CategoryFactory()
        TicketFactory.create_batch(5, created_by=requester_1)

        api_client.force_authenticate(user=requester_2)
        payload = {
            "title": "Máy chiếu phòng họp không lên hình",
            "description": "Đã thử đổi cáp HDMI nhưng vẫn không có tín hiệu.",
            "priority": "HIGH",
            "category": str(category.id),
        }

        response = api_client.post("/api/v1/tickets/", payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
