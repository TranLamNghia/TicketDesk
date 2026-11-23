from pathlib import Path

from rest_framework import serializers

# US06 KB3 / US14 KB4: attachments only accept .png / .jpg images up to 5MB.
ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5MB


def validate_image_attachment(file_obj):
    if not file_obj:
        return None

    extension = Path(file_obj.name or "").suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise serializers.ValidationError(
            "Only .png or .jpg images are accepted.", code="invalid_file_type"
        )

    if file_obj.size > MAX_ATTACHMENT_SIZE:
        raise serializers.ValidationError(
            "File size must not exceed 5MB.", code="file_too_large"
        )

    return file_obj
