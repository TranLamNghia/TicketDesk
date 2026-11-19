from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.models import Comment, TicketHistory
from apps.tickets.tests.factories import (
    CommentFactory,
    TicketFactory,
    TicketHistoryFactory,
    UserFactory,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestWhoCanComment:
    def test_any_support_can_comment_on_new_ticket(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=None)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=support)
        payload = {
            "ticket": str(ticket.id),
            "content": "Bạn gửi lại ảnh chụp rõ hơn giúp mình",
        }

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author"]["id"] == str(support.id)
        assert ticket.status_history.first().status == TicketHistory.Status.NEW

    def test_assigned_support_comment_on_processing_ticket_success(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support)
        payload = {"ticket": str(ticket.id), "content": "Mình đang kiểm tra switch."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_201_CREATED

    def test_unassigned_support_cannot_comment_on_processing_ticket(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)

        api_client.force_authenticate(user=support_b)
        payload = {"ticket": str(ticket.id), "content": "Để mình góp ý thêm."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Comment.objects.filter(ticket=ticket).exists()

    def test_unassigned_support_can_still_read_comments(self, api_client):
        support_a = UserFactory(role=User.Role.IT_SUPPORT)
        support_b = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support_a)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        CommentFactory.create_batch(2, ticket=ticket)

        api_client.force_authenticate(user=support_b)
        response = api_client.get(f"/api/v1/comments/?ticket={ticket.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_requester_cannot_comment_on_ticket_of_another_requester(self, api_client):
        requester_1 = UserFactory(role=User.Role.REQUESTER)
        requester_2 = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester_2)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=requester_1)
        payload = {"ticket": str(ticket.id), "content": "Mình cũng bị lỗi này."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_cannot_comment(self, api_client):
        manager = UserFactory(role=User.Role.IT_MANAGER)
        ticket = TicketFactory()
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.NEW)

        api_client.force_authenticate(user=manager)
        payload = {"ticket": str(ticket.id), "content": "Ưu tiên xử lý ticket này."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCommentsLockedOnFinishedTicket:
    @pytest.mark.parametrize(
        "finished_status",
        [
            TicketHistory.Status.CLOSED,
            TicketHistory.Status.REJECTED,
            TicketHistory.Status.CANCELLED,
        ],
    )
    def test_cannot_comment_on_finished_ticket(self, api_client, finished_status):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=finished_status)

        api_client.force_authenticate(user=requester)
        payload = {"ticket": str(ticket.id), "content": "Mình hỏi thêm một chút."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert not Comment.objects.filter(ticket=ticket).exists()

    def test_cannot_comment_on_ticket_solved_more_than_48_hours_ago(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=49)
        )

        api_client.force_authenticate(user=requester)
        payload = {"ticket": str(ticket.id), "content": "Mình hỏi thêm một chút."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_can_comment_on_ticket_solved_less_than_48_hours_ago(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        history = TicketHistoryFactory(
            ticket=ticket, status=TicketHistory.Status.SOLVED
        )
        TicketHistory.objects.filter(pk=history.pk).update(
            update_status_at=timezone.now() - timedelta(hours=2)
        )

        api_client.force_authenticate(user=requester)
        payload = {"ticket": str(ticket.id), "content": "Cảm ơn, mạng đã ổn."}

        response = api_client.post("/api/v1/comments/", payload)

        assert response.status_code == status.HTTP_201_CREATED

    def test_comments_of_closed_ticket_are_still_readable(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.CLOSED)
        CommentFactory.create_batch(3, ticket=ticket)

        api_client.force_authenticate(user=requester)
        response = api_client.get(f"/api/v1/comments/?ticket={ticket.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_comments_cannot_be_edited_or_deleted(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        ticket = TicketFactory(created_by=requester)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        comment = CommentFactory(ticket=ticket, author=requester)

        api_client.force_authenticate(user=requester)
        edit_response = api_client.patch(
            f"/api/v1/comments/{comment.id}/", {"content": "Sửa lại nội dung"}
        )
        delete_response = api_client.delete(f"/api/v1/comments/{comment.id}/")

        assert edit_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert delete_response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestCommentAttachment:
    def test_comment_with_image_attachment_success(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        image = SimpleUploadedFile("loi.png", b"x" * 1024, content_type="image/png")

        api_client.force_authenticate(user=requester)
        payload = {
            "ticket": str(ticket.id),
            "content": "Mình gửi thêm ảnh lỗi",
            "attachment": image,
        }

        response = api_client.post("/api/v1/comments/", payload, format="multipart")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author"]["id"] == str(requester.id)
        assert len(response.data["attachments"]) == 1
        assert response.data["attachments"][0]["size"] == 1024

    def test_comment_with_non_image_attachment_fails(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        pdf = SimpleUploadedFile("huongdan.pdf", b"%PDF-1.4")

        api_client.force_authenticate(user=support)
        payload = {
            "ticket": str(ticket.id),
            "content": "Bạn làm theo hướng dẫn này nhé",
            "attachment": pdf,
        }

        response = api_client.post("/api/v1/comments/", payload, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "attachment" in response.data
        assert not Comment.objects.filter(ticket=ticket).exists()

    def test_comment_with_attachment_over_5mb_fails(self, api_client):
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        big_image = SimpleUploadedFile("loi.jpg", b"x" * (6 * 1024 * 1024))

        api_client.force_authenticate(user=support)
        payload = {
            "ticket": str(ticket.id),
            "content": "Ảnh chụp màn hình lỗi",
            "attachment": big_image,
        }

        response = api_client.post("/api/v1/comments/", payload, format="multipart")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Comment.objects.filter(ticket=ticket).exists()

    def test_ticket_detail_shows_comment_attachments(self, api_client):
        requester = UserFactory(role=User.Role.REQUESTER)
        support = UserFactory(role=User.Role.IT_SUPPORT)
        ticket = TicketFactory(created_by=requester, assignee=support)
        TicketHistoryFactory(ticket=ticket, status=TicketHistory.Status.PROCESSING)
        image = SimpleUploadedFile("loi.png", b"x" * 512, content_type="image/png")

        api_client.force_authenticate(user=requester)
        api_client.post(
            "/api/v1/comments/",
            {"ticket": str(ticket.id), "content": "Ảnh lỗi", "attachment": image},
            format="multipart",
        )
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")

        assert len(response.data["comments"]) == 1
        assert len(response.data["comments"][0]["attachments"]) == 1
