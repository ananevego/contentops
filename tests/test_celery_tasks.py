from app.tasks import build_report_task, celery_app


def test_report_task_runs_in_celery_eager_mode(tmp_path):
    previous = celery_app.conf.task_always_eager
    celery_app.conf.update(task_always_eager=True, task_store_eager_result=True)
    try:
        result = build_report_task.delay(str(tmp_path)).get(timeout=5)
    finally:
        celery_app.conf.update(task_always_eager=previous)

    assert result["summary"]["total_items"] > 0
    assert (tmp_path / "trend_dynamics.png").is_file()
