"""
End-to-end integration tests with OpenReview server.
"""

import json
import time
import requests
import pytest
import openreview
import logging
import datetime

from matcher.service.openreview_interface import ConfigNoteInterface
from matcher.solvers import SolverException

from conftest import clean_start_conference, wait_for_status


def test_integration_basic(openreview_context, celery_app, celery_worker):
    """
    Basic integration test. Makes use of the OpenReview Builder
    """
    openreview_client = openreview_context["openreview_client"]
    test_client = openreview_context["test_client"]

    conference_id = "ICML.cc/2000/Conference"
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
        "solver": "Randomized",
        "randomized_probability_limits": "0.5",
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

    response = test_client.post(
        "/match/sync",
        data=json.dumps({"configNoteId": config_note.id}),
        content_type="application/json",
        headers=openreview_client.headers,
    )
    assert response.status_code == 200

    matcher_status = wait_for_status(openreview_client, config_note.id)
    assert matcher_status.content["status"] == "Complete"
    assert "randomized_fraction_of_opt" in matcher_status.content

    paper_assignment_edges = openreview_client.get_edges(
        label="integration-test",
        invitation=conference.get_paper_assignment_id(
            conference.get_reviewers_id()
        ),
    )

    assert len(paper_assignment_edges) == num_papers * reviews_per_paper
