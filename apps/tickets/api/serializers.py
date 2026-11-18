from rest_framework import serializers
from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)
from apps.tickets.models import (
    Category,
    Comment,
    Ticket,
    TicketHistory,
    AttachmentTicket,
    AttachmentComment,
)
from apps.tickets.selectors import get_sla_due_at, is_ticket_overdue
from apps.tickets.validators import validate_image_attachment
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


class AttachmentTicketSerializer(ModelSerializer):
    class Meta:
        model = AttachmentTicket
        fields = ["id", "url", "size"]
        read_only_fields = fields


class CommentAuthorSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role"]


class AttachmentCommentSerializer(ModelSerializer):
    class Meta:
        model = AttachmentComment
        fields = ["id", "url", "size"]
        read_only_fields = fields


class CommentSerializer(ModelSerializer):
    author = CommentAuthorSerializer(read_only=True)
    attachments = AttachmentCommentSerializer(many=True, read_only=True)
    attachment = serializers.FileField(required=False, write_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "ticket",
            "author",
            "content",
            "comment_at",
            "attachments",
            "attachment",
        ]
        read_only_fields = ["id", "author", "comment_at", "attachments"]

    def validate_attachment(self, file_obj):
        # US14 KB4: comment attachments only accept .png/.jpg up to 5MB
        return validate_image_attachment(file_obj)

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
    has_attachment = SerializerMethodField()
    sla_due_at = SerializerMethodField()
    is_overdue = SerializerMethodField()

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
            "has_attachment",
            "sla_due_at",
            "is_overdue",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        histories = obj.status_history.all()  # Retrieve data from prefetch RAM

        if histories:
            return histories[0].status

        return TicketHistory.Status.NEW

    def get_sla_due_at(self, obj):
        return serializers.DateTimeField().to_representation(get_sla_due_at(obj))

    def get_is_overdue(self, obj):
        return is_ticket_overdue(obj, self.get_status(obj))

    def get_has_attachment(self, obj):
        return obj.attachments.exists()


class TicketHistorySerializer(ModelSerializer):
    class Meta:
        model = TicketHistory
        fields = ["id", "status", "update_status_at"]
        read_only_fields = fields


class TicketDetailSerializer(TicketListSerializer):
    comments = CommentSerializer(many=True, read_only=True)
    status_history = TicketHistorySerializer(many=True, read_only=True)
    attachments = AttachmentTicketSerializer(many=True, read_only=True)

    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + [
            "description",
            "note",
            "comments",
            "status_history",
            "attachments",
        ]
        read_only_fields = fields


class TicketCreateSerializer(ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False
    )
    attachment = serializers.FileField(required=False, write_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "priority", "category", "attachment"]
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

    def validate_attachment(self, file_obj):
        return validate_image_attachment(file_obj)
