from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)
from apps.tickets.models import Category, Comment, Ticket, TicketHistory
from apps.users.models import User


class CategorySerializer(ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        clean_name = value.strip()

        if len(clean_name) < 2:
            raise ValidationError("Category Name must be at lease 2 characters long.")

        return clean_name


class CommentAuthorSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role"]


class CommentSerializer(ModelSerializer):
    author = CommentAuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "ticket", "author", "content", "comment_at"]
        read_only_fields = ["id", "author", "comment_at"]

    def validate_content(self, value):
        clean_content = value.strip()

        if not clean_content:
            raise ValidationError("Comment content cannot be empty.")

        return clean_content


class TicketUserSummarySerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role"]


class TicketListSerializer(ModelSerializer):
    category = CategorySerializer(read_only=True)
    created_by = TicketUserSummarySerializer(read_only=True)
    assignee = TicketUserSummarySerializer(read_only=True)

    status = SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "title",
            "status",
            "priority",
            "category",
            "created_by",
            "assignee",
            "created_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        histories = obj.status_history.all()  # Retrieve data from prefetch RAM

        if histories:
            return histories[0].status

        return TicketHistory.Status.NEW


class TicketHistorySerializer(ModelSerializer):
    class Meta:
        model = TicketHistory
        fields = ["id", "status", "update_status_at"]
        read_only_fields = fields


class TicketDetailSerializer(TicketListSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    status_history = TicketHistorySerializer(many=True, read_only=True)

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "description",
            "note",
            "comments",
            "status_history",
        ]
        read_only_fields = fields


class TicketCreateSerializer(ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "priority", "category"]
        read_only_fields = ["id"]

    def validate_title(self, value):
        clean_title = value.strip()

        if len(clean_title) < 5:
            raise ValidationError("Title must be at leat 5 characters long.")

        return clean_title

    def validate_description(self, value):
        clean_description = value.strip()

        if not clean_description:
            raise ValidationError("Description cannot be empty.")

        return clean_description
