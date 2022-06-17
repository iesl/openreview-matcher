"""
Defines pytest fixtures that maintain a persistent state
(in relation to the test openreview server) between tests.
"""

import os
import datetime
import time
import random
import subprocess
import requests
import pytest

import openreview

import matcher.service

AFFINITY_SCORE_FILE = "./affinity_scores"
pytest_plugins = ["celery.contrib.pytest"]


def ping_url(url):
    iterations = 300
    iteration_duration = 0.1

    for _ in range(iterations):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(iteration_duration)

    raise TimeoutError("no response within {} iterations".format(iterations))


def wait_for_status(client, config_note_id):
    """
    Repeatedly requests the configuration note until its status is not 'Initialized' or 'Running',
    then returns the status.
    """
    max_iterations = 100
    interval_duration = 0.5
    for _ in range(max_iterations):
        config_note = client.get_note(config_note_id)
        if config_note.content["status"] in [
            "Initialized",
            "Running",
            "Queued",
        ]:
            time.sleep(interval_duration)
        else:
            return config_note

    raise TimeoutError("matcher did not finish")


def initialize_superuser():
    """register and activate the superuser account"""

    requests.put(
        "http://localhost:3000/reset/openreview.net", json={"password": "1234"}
    )
    client = openreview.Client(
        baseurl="http://localhost:3000",
        username="openreview.net",
        password="1234",
    )
    return client


def clean_start_conference(
    client, conference_id, num_reviewers, num_papers, reviews_per_paper
):
    builder = openreview.conference.ConferenceBuilder(
        client, "openreview.net/Support"
    )
    builder.set_conference_id(conference_id)
    now = datetime.datetime.utcnow()
    builder.set_submission_stage(
        due_date=now + datetime.timedelta(minutes=10),
        remove_fields=["abstract", "pdf", "keywords", "TL;DR"],
        withdrawn_submission_reveal_authors=True,
        desk_rejected_submission_reveal_authors=True,
    )

    conference = builder.get_result()

    submission_invitation = client.get_invitation(
        conference.get_submission_id()
    )
    submission_invitation.reply["content"]["authorids"] = {
        "values-regex": ".*"
    }
    submission_invitation = client.post_invitation(submission_invitation)

    reviewers = set()

    # TODO: is there a better way to handle affinity scores?
    # Maybe conference.setup_matching() should allow a score matrix as input
    with open(AFFINITY_SCORE_FILE, "w") as file_handle:
        for paper_number in range(num_papers):
            authorids = [
                "testauthor{0}{1}@test.com".format(paper_number, author_code)
                for author_code in ["a", "b", "c"]
            ]
            authors = ["Author Author" for _ in ["A", "B", "C"]]
            content = {
                "title": "Test_Paper_{}".format(paper_number),
                "authors": authors,
                "authorids": authorids,
            }
            signatures = ["~Super_User1"]
            readers = [conference.id] + authorids + signatures
            writers = [conference.id] + authorids + signatures
            submission = openreview.Note(
                signatures=signatures,
                writers=writers,
                readers=readers,
                content=content,
                invitation=conference.get_submission_id(),
            )

            posted_submission = client.post_note(submission)

            for index in range(0, num_reviewers):
                reviewer = "~User{0}_Reviewer1".format(chr(97 + index))
                reviewers.add(reviewer)
                score = random.random()
                row = [
                    posted_submission.forum,
                    reviewer,
                    "{:.3f}".format(score),
                ]
                file_handle.write(",".join(row) + "\n")

    conference.setup_post_submission_stage(force=True)
    conference.set_reviewers(emails=list(reviewers))
    conference.setup_matching(
        affinity_score_file=AFFINITY_SCORE_FILE, build_conflicts=True
    )

    return conference


def assert_arrays(array_A, array_B, is_string=False):
    if is_string:
        assert all([a == b for a, b in zip(sorted(array_A), sorted(array_B))])
    else:
        assert all(
            [
                float(a) == float(b)
                for a, b in zip(sorted(array_A), sorted(array_B))
            ]
        )


@pytest.fixture(scope="session")
def openreview_context():
    """
    A pytest fixture for setting up a clean OpenReview test instance:

    1.  Opens a subprocess running `scripts/clean_start_app.js` from the OpenReview home directory.
    2.  When the OpenReview instance responds to pings, creates a super user account for testing.
    3.  Yields the process, Flask app, and openreview.Client object to the test function.

    `scope` argument is set to 'function', so each function will get a clean test instance.
    """

    app = matcher.service.create_app(
        config={
            "LOG_FILE": "pytest.log",
            "OPENREVIEW_USERNAME": "openreview.net",
            "OPENREVIEW_PASSWORD": "1234",
            "OPENREVIEW_BASEURL": "http://localhost:3000",
            "SUPERUSER_FIRSTNAME": "Super",
            "SUPERUSER_LASTNAME": "User",
            "SUPERUSER_TILDE_ID": "~Super_User1",
            "SUPERUSER_EMAIL": "info@openreview.net",
            "REDIS_ADDR": "localhost",
            "REDIS_PORT": 6379,
            "REDIS_DB": 10,
        }
    )

    superuser_client = initialize_superuser()
    for index in range(0, 26):
        openreview.tools.create_profile(
            superuser_client,
            "user{0}_reviewer@mail.com".format(chr(97 + index)),
            "User{0}".format(chr(97 + index)),
            "Reviewer",
        )
    with app.app_context():
        yield {
            "app": app,
            "test_client": app.test_client(),
            "openreview_client": superuser_client,
        }


@pytest.fixture(scope="session")
def celery_config():
    return {
        "broker_url": "redis://localhost:6379/10",
        "result_backend": "redis://localhost:6379/10",
        "task_track_started": True,
        "task_serializer": "pickle",
        "result_serializer": "pickle",
        "accept_content": ["pickle", "application/x-python-serialize"],
        "result_accept_content": ["pickle", "application/x-python-serialize"],
        "task_create_missing_queues": True,
    }


@pytest.fixture(scope="session")
def celery_includes():
    return ["matcher.service.celery_tasks", "tests.tasks"]


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "queues": ("default", "matching", "deployment", "failure", "startup"),
        "perform_ping_check": False,
        "concurrency": 4,
    }


if __name__ == "__main__":
    config = {
        "OPENREVIEW_USERNAME": "openreview.net",
        "OPENREVIEW_PASSWORD": "1234",
        "OPENREVIEW_BASEURL": "http://localhost:3000",
        "SUPERUSER_FIRSTNAME": "Super",
        "SUPERUSER_LASTNAME": "User",
        "SUPERUSER_TILDE_ID": "~Super_User1",
        "SUPERUSER_EMAIL": "info@openreview.net",
    }

    superuser_client = initialize_superuser()

    # TODO: Parameterize this
    num_reviewers, num_papers, reviews_per_paper = 50, 50, 1

    conference_id = "ICLR.cc/2019/Conference"
    conference = clean_start_conference(
        superuser_client,
        conference_id,
        num_reviewers,
        num_papers,
        reviews_per_paper,
    )
