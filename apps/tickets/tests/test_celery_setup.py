import pytest
from config.celery import app as celery_app, debug_task
from apps.tickets.tasks import auto_close_solved_tickets_task


def test_celery_app_configuration():
    assert celery_app.main == "ticketdesk"
    assert celery_app.conf.task_always_eager is True
    assert celery_app.conf.timezone == "Asia/Ho_Chi_Minh"


def test_celery_debug_task_runs_eagerly():
    result = debug_task.delay()
    assert result.successful()


@pytest.mark.django_db
def test_auto_close_solved_tickets_task_runs_successfully():
    result = auto_close_solved_tickets_task.delay()
    assert result.successful()
    assert isinstance(result.result, int)
