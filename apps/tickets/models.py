import uuid
from django.conf import settings
from django.db import models


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")

    class Meta:
        db_table = "categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, verbose_name="Title")
    description = models.TextField(verbose_name="Description")
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name="Priority",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="tickets",
        verbose_name="Category",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
        verbose_name="Created By",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Assignee",
    )
    note = models.TextField(blank=True, null=True, verbose_name="Internal Note")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tickets"
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_priority_display()}] {self.title}"


class TicketHistory(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        PROCESSING = "PROCESSING", "Processing"
        SOLVED = "SOLVED", "Solved"
        CLOSED = "CLOSED", "Closed"
        REOPEN = "REOPEN", "Reopen"
        REJECT = "REJECT", "Reject"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name="Ticket",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name="Status",
    )
    update_status_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_history"
        verbose_name = "Ticket History"
        verbose_name_plural = "Ticket Histories"
        ordering = ["-update_status_at"]

    def __str__(self) -> str:
        return f"{self.ticket.title} -> {self.get_status_display()}"


class AssignmentHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="assignment_history",
        verbose_name="Ticket",
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignments_sent",
        verbose_name="Sent By",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignments_received",
        verbose_name="Received By",
    )
    reason = models.TextField(verbose_name="Transfer Reason")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "assignment_history"
        verbose_name = "Assignment History"
        verbose_name_plural = "Assignment Histories"
        ordering = ["-assigned_at"]

    def __str__(self) -> str:
        return f"{self.ticket.title}: {self.sent_by} -> {self.received_by}"


class AttachmentTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Ticket",
    )
    url = models.FileField(
        upload_to="attachments/tickets/%Y/%m/",
        verbose_name="Attachment",
    )
    size = models.PositiveIntegerField(
        help_text="File size in bytes",
        verbose_name="File Size",
    )

    class Meta:
        db_table = "attachment_ticket"
        verbose_name = "Ticket Attachment"
        verbose_name_plural = "Ticket Attachments"

    def __str__(self) -> str:
        return f"Attachment of Ticket: {self.ticket.title}"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Ticket",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
        verbose_name="Author",
    )
    content = models.TextField(verbose_name="Comment Content")
    comment_at = models.DateTimeField(auto_now_add=True, verbose_name="Comment Time")

    class Meta:
        db_table = "comments"
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ["comment_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author} on {self.ticket.title}"


class AttachmentComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Comment",
    )
    url = models.FileField(
        upload_to="attachments/comments/%Y/%m/",
        verbose_name="Attachment",
    )
    size = models.PositiveIntegerField(
        help_text="File size in bytes",
        verbose_name="File Size",
    )

    class Meta:
        db_table = "attachment_comment"
        verbose_name = "Comment Attachment"
        verbose_name_plural = "Comment Attachments"

    def __str__(self) -> str:
        return f"Attachment of Comment: {self.comment.id}"
