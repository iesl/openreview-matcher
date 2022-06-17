from kombu import Exchange, Queue
from kombu.serialization import registry

task_default_queue = "default"
task_queues = (
    Queue("matching", routing_key="matcher.service.celery_tasks.run_matching"),
    Queue(
        "deployment", routing_key="matcher.service.celery_tasks.run_deployment"
    ),
    Queue(
        "failure", routing_key="matcher.service.celery_tasks.set_error_status"
    ),
    Queue(
        "startup",
        routing_key="matcher.service.celery_tasks.cancel_stale_notes",
    ),
    Queue("default"),
)
task_ignore_result = False
broker_url = "redis://localhost:6379/10"
result_backend = "redis://localhost:6379/10"
task_serializer = "pickle"
result_serializer = "pickle"
accept_content = ["pickle", "application/x-python-serialize"]
result_accept_content = ["pickle", "application/x-python-serialize"]
task_create_missing_queues = True

registry.enable("pickle")
registry.enable("application/x-python-serialize")
