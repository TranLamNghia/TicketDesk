import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tickets.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestLogout:
    def test_logout_revokes_refresh_token(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")
        tokens = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "Matkhau123"},
        ).data

        logout_response = api_client.post(
            "/api/v1/auth/logout/", {"refresh": tokens["refresh"]}
        )
        refresh_response = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}
        )

        assert logout_response.status_code == status.HTTP_200_OK
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_twice_with_same_token_fails(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")
        tokens = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "Matkhau123"},
        ).data
        api_client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]})

        response = api_client.post(
            "/api/v1/auth/logout/", {"refresh": tokens["refresh"]}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_invalid_token_fails(self, api_client):
        response = api_client.post("/api/v1/auth/logout/", {"refresh": "abc.def.ghi"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_old_refresh_token_is_revoked_after_rotation(self, api_client):
        UserFactory(username="requester01", password="Matkhau123")
        tokens = api_client.post(
            "/api/v1/auth/token/",
            {"username": "requester01", "password": "Matkhau123"},
        ).data
        first_refresh = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}
        )

        reuse_response = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}
        )

        assert first_refresh.status_code == status.HTTP_200_OK
        assert "refresh" in first_refresh.data
        assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED
