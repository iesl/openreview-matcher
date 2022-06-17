import json

import redis
from openreview import openreview

from matcher.service.celery_tasks import run_matching, cancel_stale_notes
from matcher.service.openreview_interface import ConfigNoteInterface
from tests.conftest import clean_start_conference, wait_for_status


def test_matching_task(openreview_context, celery_app, celery_worker):
    openreview_client = openreview_context["openreview_client"]
    test_client = openreview_context["test_client"]
    app = openreview_context["app"]

    conference_id = "ICLR.cc/2018x/Conference"
    num_reviewers = 10
    num_papers = 10
    reviews_per_paper = 3
    max_papers = 5
    min_papers = 1
    alternates = 0

    conference = clean_start_conference(
        openreview_client,
        conference_id,
        num_reviewers,
        num_papers,
        reviews_per_paper,
    )

    reviewers_id = conference.get_reviewers_id()

    config = {
        "title": "integration-test",
        "user_demand": str(reviews_per_paper),
        "max_papers": str(max_papers),
        "min_papers": str(min_papers),
        "alternates": str(alternates),
        "config_invitation": "{}/-/Assignment_Configuration".format(
            reviewers_id
        ),
        "paper_invitation": conference.get_blind_submission_id(),
        "assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id
        ),
        "deployed_assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id, deployed=True
        ),
        "invite_assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id, invite=True
        ),
        "aggregate_score_invitation": "{}/-/Aggregate_Score".format(
            reviewers_id
        ),
        "conflicts_invitation": conference.get_conflict_score_id(reviewers_id),
        "custom_max_papers_invitation": "{}/-/Custom_Max_Papers".format(
            reviewers_id
        ),
        "match_group": reviewers_id,
        "scores_specification": {
            conference.get_affinity_score_id(reviewers_id): {
                "weight": 1.0,
                "default": 0.0,
            }
        },
        "status": "Initialized",
        "solver": "MinMax",
    }

    config_note = openreview.Note(
        **{
            "invitation": "{}/-/Assignment_Configuration".format(reviewers_id),
            "readers": [conference.get_id()],
            "writers": [conference.get_id()],
            "signatures": [conference.get_id()],
            "content": config,
        }
    )

    config_note = openreview_client.post_note(config_note)
    assert config_note

    interface = ConfigNoteInterface(
        client=openreview_client,
        config_note_id=config_note.id,
        logger=app.logger,
    )
    solver_class = interface.config_note.content.get("solver", "MinMax")
    task = run_matching.s(interface, solver_class, app.logger).apply()

    matcher_status = wait_for_status(openreview_client, config_note.id)
    assert matcher_status.content["status"] == "Complete"
    assert task.status == "SUCCESS"

    paper_assignment_edges = openreview_client.get_edges(
        label="integration-test",
        invitation=conference.get_paper_assignment_id(
            conference.get_reviewers_id()
        ),
    )

    assert len(paper_assignment_edges) == num_papers * reviews_per_paper


def test_cancel_stale_tasks(openreview_context, celery_app, celery_worker):
    openreview_client = openreview_context["openreview_client"]

    conference_id = "ICLR.cc/2018x/Conference"
    num_reviewers = 10
    num_papers = 10
    reviews_per_paper = 3
    max_papers = 5
    min_papers = 1
    alternates = 0

    conference = clean_start_conference(
        openreview_client,
        conference_id,
        num_reviewers,
        num_papers,
        reviews_per_paper,
    )

    reviewers_id = conference.get_reviewers_id()

    config = {
        "title": "integration-test-2",
        "user_demand": str(reviews_per_paper),
        "max_papers": str(max_papers),
        "min_papers": str(min_papers),
        "alternates": str(alternates),
        "config_invitation": "{}/-/Assignment_Configuration".format(
            reviewers_id
        ),
        "paper_invitation": conference.get_blind_submission_id(),
        "assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id
        ),
        "deployed_assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id, deployed=True
        ),
        "invite_assignment_invitation": conference.get_paper_assignment_id(
            reviewers_id, invite=True
        ),
        "aggregate_score_invitation": "{}/-/Aggregate_Score".format(
            reviewers_id
        ),
        "conflicts_invitation": conference.get_conflict_score_id(reviewers_id),
        "custom_max_papers_invitation": "{}/-/Custom_Max_Papers".format(
            reviewers_id
        ),
        "match_group": reviewers_id,
        "scores_specification": {
            conference.get_affinity_score_id(reviewers_id): {
                "weight": 1.0,
                "default": 0.0,
            }
        },
        "status": "Running",
        "solver": "MinMax",
    }

    config_note = openreview.Note(
        **{
            "invitation": "{}/-/Assignment_Configuration".format(reviewers_id),
            "readers": [conference.get_id()],
            "writers": [conference.get_id()],
            "signatures": [conference.get_id()],
            "content": config,
        }
    )

    config_note = openreview_client.post_note(config_note)
    assert config_note

    redis_con = redis.Redis(
        host="localhost", port=6379, db=10, decode_responses=True
    )
    redis_con.hset("config_notes", config_note.id, "Running")

    task = cancel_stale_notes.s(
        "http://localhost:3000", "openreview.net", "1234"
    ).apply()

    matcher_status = wait_for_status(openreview_client, config_note.id)
    assert matcher_status.content["status"] == "Cancelled"
    assert task.status == "SUCCESS"

    assert redis_con.hget("config_notes", config_note.id) == "Cancelled"
