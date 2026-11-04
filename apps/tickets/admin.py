from django.contrib import admin

from .models import (
    AssignmentHistory,
    AttachmentComment,
    AttachmentTicket,
    Category,
    Comment,
    Ticket,
    TicketHistory,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "id")
    search_fields = ("name",)


class TicketHistoryInline(admin.TabularInline):
    model = TicketHistory
    extra = 0
    readonly_fields = ("status", "update_status_at")
    can_delete = False


class AttachmentTicketInline(admin.TabularInline):
    model = AttachmentTicket
    extra = 0


class CommentInline(admin.StackedInline):
    model = Comment
    extra = 0
    readonly_fields = ("comment_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "priority",
        "category",
        "created_by",
        "assignee",
        "created_at",
    )
    list_filter = ("priority", "category", "created_at")
    search_fields = (
        "title",
        "description",
        "created_by__username",
        "assignee__username",
    )
    readonly_fields = ("created_at", "id")
    inlines = [TicketHistoryInline, AttachmentTicketInline, CommentInline]


@admin.register(TicketHistory)
class TicketHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "status", "update_status_at")
    list_filter = ("status", "update_status_at")
    search_fields = ("ticket__title",)
    readonly_fields = ("update_status_at",)


@admin.register(AssignmentHistory)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sent_by", "received_by", "assigned_at")
    search_fields = (
        "ticket__title",
        "sent_by__username",
        "received_by__username",
    )
    readonly_fields = ("assigned_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "comment_at")
    search_fields = ("content", "author__username", "ticket__title")
    readonly_fields = ("comment_at",)


@admin.register(AttachmentTicket)
class AttachmentTicketAdmin(admin.ModelAdmin):
    list_display = ("ticket", "url", "size")


@admin.register(AttachmentComment)
class AttachmentCommentAdmin(admin.ModelAdmin):
    list_display = ("comment", "url", "size")
