from django.core.exceptions import ValidationError


class LetterAndDigitPasswordValidator:
    message = "Password must contain both letters and digits."

    def validate(self, password, user=None):
        has_letter = any(char.isalpha() for char in password)
        has_digit = any(char.isdigit() for char in password)
        if not (has_letter and has_digit):
            raise ValidationError(self.message, code="password_no_letter_or_digit")

    def get_help_text(self):
        return self.message
