import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        REQUESTER = ("REQUESTER", "Requester")

        IT_SUPPORT = ("IT_SUPPORT", "IT Support")

        IT_MANAGER = ("IT_MANAGER", "IT Manager")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.REQUESTER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_requester(self):
        return self.role == self.Role.REQUESTER

    @property
    def is_it_support(self):
        return self.role == self.Role.IT_SUPPORT

    @property
    def is_it_manager(self):
        return self.role == self.Role.IT_MANAGER
