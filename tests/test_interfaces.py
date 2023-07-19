import random
from unittest import mock
import pytest
import openreview
from matcher.service.openreview_interface import ConfigNoteInterfaceV1
from conftest import assert_arrays
from matcher.core import MatcherStatus


def mock_client(
    paper_ids,
    reviewer_ids,
    mock_invitations,
    mock_groups,
    mock_notes,
    mock_grouped_edges,
    mock_profiles,
):

    client = mock.MagicMock(openreview.Client)

    def get_invitation(id):
        return mock_invitations[id]

    def get_group(id):
        return mock_groups[id]

    def get_note(id):
        return mock_notes[id]

    def get_notes(invitation, limit=1000, offset=0, **kwargs):
        if kwargs.get('with_count'):
            return mock_notes[invitation][offset : offset + limit], len(mock_notes[invitation])
        else:
            return mock_notes[invitation][offset : offset + limit]

    def post_note(note):
        mock_notes[note.id] = note
        return mock_notes[note.id]

    def get_grouped_edges(invitation, limit=1000, offset=0, **kwargs):
        return mock_grouped_edges[invitation][offset : offset + limit]

    def search_profiles(ids):
        profiles = []
        for id in ids:
            profiles.append(mock_profiles[id])
        return profiles

    client.get_invitation = mock.MagicMock(side_effect=get_invitation)
    client.get_group = mock.MagicMock(side_effect=get_group)
    client.get_note = mock.MagicMock(side_effect=get_note)
    client.get_notes = mock.MagicMock(side_effect=get_notes)
    client.post_note = mock.MagicMock(side_effect=post_note)
    client.get_grouped_edges = mock.MagicMock(side_effect=get_grouped_edges)
    client.search_profiles = mock.MagicMock(side_effect=search_profiles)

    return client


def test_confignote_interface():
    """Test of basic ConfigNoteInterfaceV1 functionality."""

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 2,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "default": 0.5,
                            "weight": 2,
                            "translate_map": {"High": 1, "Very Low": -1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "Very Low",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "Very Low",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "Very Low",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 1},
                        {"tail": "~reviewer3", "weight": 3},
                    ],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.config_note
    assert_arrays(
        interface.reviewers,
        ["~reviewer0", "~reviewer1", "~reviewer2", "~reviewer3"],
        is_string=True,
    )
    assert_arrays(
        interface.papers, ["paper0", "paper1", "paper2"], is_string=True
    )
    assert_arrays(interface.minimums, [1, 1, 1, 1])
    assert_arrays(interface.maximums, [1, 2, 2, 2])
    assert_arrays(interface.demands, [1, 1, 1])
    assert interface.constraints
    valid_constraint_pairs = [
        ("paper0", "~reviewer1"),
        ("paper1", "~reviewer2"),
        ("paper2", "~reviewer3"),
    ]
    for (paper, reviewer, constraint) in interface.constraints:
        if (paper, reviewer) in valid_constraint_pairs:
            assert constraint == 1
        else:
            assert constraint == 0
    assert interface.scores_by_type
    assert len(interface.scores_by_type) == 2
    map_defaults = {"<bid_invitation>": 0.5, "<affinity_score_invitation>": 0}
    for invitation, scores in interface.scores_by_type.items():
        assert "edges" in scores
        assert "default" in scores
        assert map_defaults[invitation] == scores["default"]
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]

    very_low_bids = [
        ("paper0", "~reviewer2"),
        ("paper1", "~reviewer3"),
        ("paper2", "~reviewer0"),
    ]
    high_bids = [
        ("paper0", "~reviewer0"),
        ("paper0", "~reviewer3"),
        ("paper1", "~reviewer0"),
        ("paper1", "~reviewer1"),
        ("paper2", "~reviewer1"),
        ("paper2", "~reviewer2"),
    ]
    for paper, reviewer, bid in interface.scores_by_type["<bid_invitation>"][
        "edges"
    ]:
        if (paper, reviewer) in very_low_bids:
            assert bid == -1
        elif (paper, reviewer) in high_bids:
            assert bid == 1

    for invitation in interface.weight_by_type:
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]
    assert_arrays(list(interface.weight_by_type.values()), [1, 2])

    assert len(interface.weight_by_type) == 2
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"


def test_confignote_interface_backward_compat_max_users():
    """Test of basic ConfigNoteInterfaceV1 functionality."""

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "max_users": 1,
                    "min_papers": 1,
                    "max_papers": 2,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "default": 0.5,
                            "weight": 2,
                            "translate_map": {"High": 1, "Very Low": -1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "Very Low",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "Very Low",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "Very Low",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 1},
                        {"tail": "~reviewer3", "weight": 3},
                    ],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.config_note
    assert_arrays(
        interface.reviewers,
        ["~reviewer0", "~reviewer1", "~reviewer2", "~reviewer3"],
        is_string=True,
    )
    assert_arrays(
        interface.papers, ["paper0", "paper1", "paper2"], is_string=True
    )
    assert_arrays(interface.minimums, [1, 1, 1, 1])
    assert_arrays(interface.maximums, [1, 2, 2, 2])
    assert_arrays(interface.demands, [1, 1, 1])
    assert interface.constraints
    valid_constraint_pairs = [
        ("paper0", "~reviewer1"),
        ("paper1", "~reviewer2"),
        ("paper2", "~reviewer3"),
    ]
    for (paper, reviewer, constraint) in interface.constraints:
        if (paper, reviewer) in valid_constraint_pairs:
            assert constraint == 1
        else:
            assert constraint == 0
    assert interface.scores_by_type
    assert len(interface.scores_by_type) == 2
    map_defaults = {"<bid_invitation>": 0.5, "<affinity_score_invitation>": 0}
    for invitation, scores in interface.scores_by_type.items():
        assert "edges" in scores
        assert "default" in scores
        assert map_defaults[invitation] == scores["default"]
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]

    very_low_bids = [
        ("paper0", "~reviewer2"),
        ("paper1", "~reviewer3"),
        ("paper2", "~reviewer0"),
    ]
    high_bids = [
        ("paper0", "~reviewer0"),
        ("paper0", "~reviewer3"),
        ("paper1", "~reviewer0"),
        ("paper1", "~reviewer1"),
        ("paper2", "~reviewer1"),
        ("paper2", "~reviewer2"),
    ]
    for paper, reviewer, bid in interface.scores_by_type["<bid_invitation>"][
        "edges"
    ]:
        if (paper, reviewer) in very_low_bids:
            assert bid == -1
        elif (paper, reviewer) in high_bids:
            assert bid == 1

    for invitation in interface.weight_by_type:
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]
    assert_arrays(list(interface.weight_by_type.values()), [1, 2])

    assert len(interface.weight_by_type) == 2
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"


def test_confignote_interface_custom_demand_edges():
    """Test of basic ConfigNoteInterfaceV1 functionality."""

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_user_demand_invitation>": openreview.Invitation(
                id="<custom_user_demand_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 2,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "weight": 1,
                            "translate_map": {"High": 1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "custom_user_demand_invitation": "<custom_user_demand_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 1},
                        {"tail": "~reviewer1", "weight": 2},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                }
            ],
            "<custom_user_demand_invitation_id>": [
                {
                    "id": {"tail": "<match_group_id>"},
                    "values": [
                        {"head": "paper0", "weight": 2},
                        {"head": "paper1", "weight": 1},
                        {"head": "paper2", "weight": 0},
                    ],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.reviewers
    assert interface.config_note
    assert interface.papers
    assert interface.minimums
    assert interface.maximums
    assert interface.demands
    assert list(interface.constraints)
    assert interface.scores_by_type
    assert interface.weight_by_type
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    assert_arrays(interface.minimums, [1, 1, 1, 0])
    assert_arrays(interface.maximums, [1, 2, 1, 0])
    assert_arrays(interface.demands, [2, 1, 0])

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"


def test_confignote_missing_edges_spec():
    """Test of basic ConfigNoteInterfaceV1 functionality."""

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 1,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {
                            "default": 2.0,
                            "weight": 1,
                        },
                        "<bid_invitation>": {
                            "default": 2.0,
                            "weight": 1,
                            "translate_map": {"High": 1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [{"tail": "~reviewer0", "weight": 1}],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.reviewers
    assert interface.config_note
    assert interface.papers
    assert interface.minimums
    assert interface.maximums
    assert interface.demands
    assert list(interface.constraints)
    assert interface.scores_by_type
    assert interface.weight_by_type
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"

    for _, scores in interface.scores_by_type.items():
        assert "default" in scores


def test_confignote_interface_no_scores_spec():
    """
    Test of basic ConfigNoteInterfaceV1 functionality when the scores spec is missing.
    """

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 1,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [{"tail": "~reviewer0", "weight": 1}],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.reviewers
    assert interface.config_note
    assert interface.papers
    assert interface.minimums
    assert interface.maximums
    assert interface.demands
    assert list(interface.constraints)
    assert not interface.scores_by_type
    assert not interface.weight_by_type
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"


def test_confignote_interface_custom_load_negative():
    """
    Reviewer 0 has a custom load of -9.4, and high scores across the board.

    Custom load should be treated as 0. Reviewer 0 should not be assigned any papers.
    """

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 1,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "weight": 1,
                            "translate_map": {"High": 1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [{"tail": "~reviewer0", "weight": -9.4}],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    for reviewer_index, reviewer in enumerate(interface.reviewers):
        if reviewer == "~reviewer0":
            assert interface.maximums[reviewer_index] == 0
        else:
            assert (
                interface.maximums[reviewer_index]
                == interface.config_note.content["max_papers"]
            )


def test_confignote_interface_custom_overload():
    """
    Default maximum number of assignments per reviewer is 1,
    but reviewer 3 has a custom load of 3. We should use the minimum of both.

    """

    mock_openreview_data = {
        "paper_ids": ["paper0", "paper1", "paper2"],
        "reviewer_ids": [
            "~reviewer0",
            "~reviewer1",
            "~reviewer2",
            "~reviewer3",
        ],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=[
                    "~reviewer0",
                    "~reviewer1",
                    "~reviewer2",
                    "~reviewer3",
                ],
            )
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<venue/-/paper_invitation_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 1,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "weight": 1,
                            "translate_map": {"High": 1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            ),
            "<venue/-/paper_invitation_id>": [
                openreview.Note(
                    id="paper0",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper1",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
                openreview.Note(
                    id="paper2",
                    readers=[],
                    writers=[],
                    signatures=[],
                    invitation="<venue/-/paper_invitation_id>",
                    content={},
                ),
            ],
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": random.random()},
                        {"tail": "~reviewer1", "weight": random.random()},
                        {"tail": "~reviewer2", "weight": random.random()},
                        {"tail": "~reviewer3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {
                            "tail": "~reviewer0",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer1",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer2",
                            "weight": None,
                            "label": "High",
                        },
                        {
                            "tail": "~reviewer3",
                            "weight": None,
                            "label": "High",
                        },
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "paper0"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 1},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper1"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 1},
                        {"tail": "~reviewer3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "paper2"},
                    "values": [
                        {"tail": "~reviewer0", "weight": 0},
                        {"tail": "~reviewer1", "weight": 0},
                        {"tail": "~reviewer2", "weight": 0},
                        {"tail": "~reviewer3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [{"tail": "~reviewer3", "weight": 3}],
                }
            ],
        },
        "mock_profiles": {
            "<profile_id>": openreview.Profile(id="<profile_id>")
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    for reviewer_index, reviewer in enumerate(interface.reviewers):
        if reviewer == "~reviewer3":
            assert interface.maximums[reviewer_index] == 1
        else:
            assert (
                interface.maximums[reviewer_index]
                == interface.config_note.content["max_papers"]
            )


def test_confignote_interface_matching_users():
    """Test of basic ConfigNoteInterfaceV1 functionality."""

    mock_openreview_data = {
        "paper_ids": ["~ac0", "~ac1", "~ac2"],
        "reviewer_ids": ["~sac0", "~sac1", "~sac2", "~sac3"],
        "mock_invitations": {
            "<assignment_invitation_id>": openreview.Invitation(
                id="<assignment_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<aggregate_score_invitation_id>": openreview.Invitation(
                id="<aggregate_score_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<custom_max_papers_invitation_id>": openreview.Invitation(
                id="<custom_max_papers_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<conflicts_invitation_id>": openreview.Invitation(
                id="<conflicts_invitation_id>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<affinity_score_invitation>": openreview.Invitation(
                id="<affinity_score_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
            "<bid_invitation>": openreview.Invitation(
                id="<bid_invitation>",
                writers=[],
                readers=[],
                signatures=[],
                reply={},
            ),
        },
        "mock_groups": {
            "<match_group_id>": openreview.Group(
                id="<match_group_id>",
                writers=[],
                readers=[],
                signatures=[],
                signatories=[],
                members=["~sac0", "~sac1", "~sac2", "~sac3"],
            ),
            "<ac_group_id>": openreview.Group(
                id="<ac_group_id>",
                readers=[],
                writers=[],
                signatures=[],
                members=["~ac0", "~ac1", "~ac2"],
                signatories=[],
            ),
        },
        "mock_notes": {
            "<config_note_id>": openreview.Note(
                id="<config_note_id>",
                readers=[],
                writers=[],
                signatures=["<match_group_id>"],
                invitation="<config_note_invitation>",
                content={
                    "title": "test-1",
                    "match_group": "<match_group_id>",
                    "paper_invitation": "<ac_group_id>",
                    "user_demand": 1,
                    "min_papers": 1,
                    "max_papers": 2,
                    "alternates": 1,
                    "conflicts_invitation": "<conflicts_invitation_id>",
                    "scores_specification": {
                        "<affinity_score_invitation>": {"weight": 1},
                        "<bid_invitation>": {
                            "default": 0.5,
                            "weight": 2,
                            "translate_map": {"High": 1, "Very Low": -1},
                        },
                    },
                    "assignment_invitation": "<assignment_invitation_id>",
                    "aggregate_score_invitation": "<aggregate_score_invitation_id>",
                    "custom_max_papers_invitation": "<custom_max_papers_invitation_id>",
                    "status": None,
                },
            )
        },
        "mock_grouped_edges": {
            "<affinity_score_invitation>": [
                {
                    "id": {"head": "~ac0"},
                    "values": [
                        {"tail": "~sac0", "weight": random.random()},
                        {"tail": "~sac1", "weight": random.random()},
                        {"tail": "~sac2", "weight": random.random()},
                        {"tail": "~sac3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "~ac1"},
                    "values": [
                        {"tail": "~sac0", "weight": random.random()},
                        {"tail": "~sac1", "weight": random.random()},
                        {"tail": "~sac2", "weight": random.random()},
                        {"tail": "~sac3", "weight": random.random()},
                    ],
                },
                {
                    "id": {"head": "~ac2"},
                    "values": [
                        {"tail": "~sac0", "weight": random.random()},
                        {"tail": "~sac1", "weight": random.random()},
                        {"tail": "~sac2", "weight": random.random()},
                        {"tail": "~sac3", "weight": random.random()},
                    ],
                },
            ],
            "<bid_invitation>": [
                {
                    "id": {"head": "~ac0"},
                    "values": [
                        {"tail": "~sac0", "weight": None, "label": "High"},
                        {"tail": "~sac2", "weight": None, "label": "Very Low"},
                        {"tail": "~sac3", "weight": None, "label": "High"},
                    ],
                },
                {
                    "id": {"head": "~ac1"},
                    "values": [
                        {"tail": "~sac0", "weight": None, "label": "High"},
                        {"tail": "~sac1", "weight": None, "label": "High"},
                        {"tail": "~sac3", "weight": None, "label": "Very Low"},
                    ],
                },
                {
                    "id": {"head": "~ac2"},
                    "values": [
                        {"tail": "~sac0", "weight": None, "label": "Very Low"},
                        {"tail": "~sac1", "weight": None, "label": "High"},
                        {"tail": "~sac2", "weight": None, "label": "High"},
                        {"tail": "~sac3", "weight": None, "label": "High"},
                    ],
                },
            ],
            "<conflicts_invitation_id>": [
                {
                    "id": {"head": "~ac0"},
                    "values": [
                        {"tail": "~sac0", "weight": 0},
                        {"tail": "~sac1", "weight": 1},
                        {"tail": "~sac2", "weight": 0},
                        {"tail": "~sac3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "~ac1"},
                    "values": [
                        {"tail": "~sac0", "weight": 0},
                        {"tail": "~sac1", "weight": 0},
                        {"tail": "~sac2", "weight": 1},
                        {"tail": "~sac3", "weight": 0},
                    ],
                },
                {
                    "id": {"head": "~ac2"},
                    "values": [
                        {"tail": "~sac0", "weight": 0},
                        {"tail": "~sac1", "weight": 0},
                        {"tail": "~sac2", "weight": 0},
                        {"tail": "~sac3", "weight": 1},
                    ],
                },
            ],
            "<custom_max_papers_invitation_id>": [
                {
                    "id": {"head": "<match_group_id>"},
                    "values": [
                        {"tail": "~sac0", "weight": 1},
                        {"tail": "~sac3", "weight": 3},
                    ],
                }
            ],
        },
        "mock_profiles": {
            "~ac0": openreview.Profile(
                id="~ac0", content={"names": [{"username": "~ac0"}]}
            ),
            "~ac1": openreview.Profile(
                id="~ac1", content={"names": [{"username": "~ac1"}]}
            ),
            "~ac2": openreview.Profile(
                id="~ac2", content={"names": [{"username": "~ac2"}]}
            ),
        },
    }

    client = mock_client(**mock_openreview_data)

    interface = ConfigNoteInterfaceV1(client, "<config_note_id>")

    assert interface.config_note
    assert_arrays(
        interface.reviewers,
        ["~sac0", "~sac1", "~sac2", "~sac3"],
        is_string=True,
    )
    assert_arrays(interface.papers, ["~ac0", "~ac1", "~ac2"], is_string=True)
    assert_arrays(interface.minimums, [1, 1, 1, 1])
    assert_arrays(interface.maximums, [1, 2, 2, 2])
    assert_arrays(interface.demands, [1, 1, 1])
    assert interface.constraints
    valid_constraint_pairs = [
        ("~ac0", "~sac1"),
        ("~ac1", "~sac2"),
        ("~ac2", "~sac3"),
    ]
    for (ac, sac, constraint) in interface.constraints:
        if (ac, sac) in valid_constraint_pairs:
            assert constraint == 1
        else:
            assert constraint == 0
    assert interface.scores_by_type
    assert len(interface.scores_by_type) == 2
    map_defaults = {"<bid_invitation>": 0.5, "<affinity_score_invitation>": 0}
    for invitation, scores in interface.scores_by_type.items():
        assert "edges" in scores
        assert "default" in scores
        assert map_defaults[invitation] == scores["default"]
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]

    very_low_bids = [("~ac0", "~sac2"), ("~ac1", "~sac3"), ("~ac2", "~sac0")]
    high_bids = [
        ("acr0", "~sac0"),
        ("~ac0", "~sac3"),
        ("~ac1", "~sac0"),
        ("~ac1", "~sac1"),
        ("~ac2", "~sac1"),
        ("~ac2", "~sac2"),
    ]
    for ac, sac, bid in interface.scores_by_type["<bid_invitation>"]["edges"]:
        if (ac, sac) in very_low_bids:
            assert bid == -1
        elif (ac, sac) in high_bids:
            assert bid == 1

    for invitation in interface.weight_by_type:
        assert invitation in [
            "<bid_invitation>",
            "<affinity_score_invitation>",
        ]
    assert_arrays(list(interface.weight_by_type.values()), [1, 2])

    assert len(interface.weight_by_type) == 2
    assert interface.assignment_invitation
    assert interface.aggregate_score_invitation

    interface.set_status(MatcherStatus.RUNNING)
    assert interface.config_note.content["status"] == "Running"
