import logging

import redis
from openreview import openreview
from requests.exceptions import ConnectionError
from urllib3.exceptions import ConnectTimeoutError, RequestError

from matcher import Matcher
from matcher.core import MatcherStatus
from matcher.service.openreview_interface import (
    ConfigNoteInterface,
    Deployment,
)
from matcher.service.server import celery_app as celery


def on_task_failure(self, exc, task_id, args, kwargs, einfo):
    if kwargs:
        logger = kwargs["logger"]
        interface = kwargs["interface"]
        logger.warn(
            "{} task for config note {} failed.".format(
                self.name, interface.config_note.id
            )
        )
        set_error_status.apply_async(
            kwargs={"interface": interface, "logger": logger, "exc": exc},
            queue="failure",
            ignore_result=True,
        )


@celery.task(
    name="error_status",
    track_started=True,
    bind=True,
    time_limit=3600 * 24,
    autoretry_for=(Exception,),
    retry_backoff=10,
    max_retries=15,
    retry_jitter=True,
)
def set_error_status(self, interface: ConfigNoteInterface, logger, exc):
    logger.info(
        "Setting status for config note {} to Error.".format(
            interface.config_note.id
        )
    )
    interface.set_status(MatcherStatus.ERROR, message=str(type(exc)))


@celery.task(
    name="matching",
    track_started=True,
    bind=True,
    time_limit=3600 * 24,
    on_failure=on_task_failure,
)
def run_matching(
    self,
    interface: ConfigNoteInterface,
    solver_class: str,
    logger: logging.Logger,
):
    logger.debug(
        "{} task received for config note {}".format(
            self.name, interface.config_note.id
        )
    )
    matcher = Matcher(
        datasource=interface, solver_class=solver_class, logger=logger
    )
    try:
        matcher.run()
        return matcher.get_status()
    except (
        ConnectionError,
        ConnectTimeoutError,
        RequestError,
        ConnectionRefusedError,
    ) as exc:
        raise self.retry(
            exc=exc, countdown=300 * (self.request.retries + 1), max_retries=3
        )


@celery.task(
    name="deployment",
    track_started=True,
    bind=True,
    time_limit=3600 * 24,
    on_failure=on_task_failure,
)
def run_deployment(
    self, interface: ConfigNoteInterface, logger: logging.Logger
):
    deployment = Deployment(config_note_interface=interface, logger=logger)
    try:
        deployment.run()
        return interface.config_note.content["status"]
    except (
        ConnectionError,
        ConnectTimeoutError,
        RequestError,
        ConnectionRefusedError,
    ) as exc:
        raise self.retry(
            exc=exc, countdown=300 * (self.request.retries + 1), max_retries=1
        )


@celery.task(name="cancel_stale_notes", track_started=True, bind=True)
def cancel_stale_notes(
    self, openreview_baseurl, openreview_username, openreview_password
):
    print("Cancelling Stale Notes")
    from matcher.service.server import redis_pool

    redis_conn = redis.Redis(connection_pool=redis_pool)
    config_notes = redis_conn.hgetall(name="config_notes")
    openreview_client = openreview.Client(
        baseurl=openreview_baseurl,
        username=openreview_username,
        password=openreview_password,
    )
    for note_id, status in config_notes.items():
        if status in ["Running", "Deploying", "Queued"]:
            config_note = openreview_client.get_note(note_id)
            redis_conn.hset(
                name="config_notes",
                key=note_id,
                value=MatcherStatus.CANCELLED.value,
            )
            config_note.content["status"] = MatcherStatus.CANCELLED.value
            config_note.content[
                "error_message"
            ] = "Matching run was cancelled, please try again or contact support."
            openreview_client.post_note(config_note)
            print(
                "Config Note {} status set to: {}".format(
                    config_note.id, config_note.content["status"]
                )
            )
    redis_conn.close()
