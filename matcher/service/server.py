from celery.signals import worker_ready

from matcher.service import create_app, create_celery, create_redis

app = create_app()
celery_app = create_celery(app)
redis_pool = create_redis(app)


@worker_ready.connect
def at_start(sender, **kwargs):
    with sender.app.connection() as conn:
        task_kwargs = {
            "openreview_baseurl": sender.app.conf["OPENREVIEW_BASEURL"],
            "openreview_username": sender.app.conf["OPENREVIEW_USERNAME"],
            "openreview_password": sender.app.conf["OPENREVIEW_PASSWORD"],
        }
        sender.app.send_task("cancel_stale_notes", kwargs=task_kwargs)
