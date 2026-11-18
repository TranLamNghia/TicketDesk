from rest_framework.serializers import ModelSerializer, SerializerMethodField

from apps.users.models import User


class ITSupportSerializer(ModelSerializer):
    current_ticket = SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_active", "current_ticket"]
        read_only_fields = fields

    def get_current_ticket(self, obj):
        ticket_id = getattr(obj, "current_ticket_id", None)
        if ticket_id is None:
            return None
        return {"id": str(ticket_id), "title": obj.current_ticket_title}
