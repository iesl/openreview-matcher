"""
Verifies that custom loads are being used correctly in the matcher.

"""
import itertools
import random
from unittest.mock import patch

import pytest
import logging
from numpy import testing as nptest
from matcher import Matcher


def test_matcher_basic_minmax():
    reviewers = ["reviewer1", "reviewer2", "reviewer3"]
    papers = ["paper1", "paper2", "paper3"]

    scores = [
        (paper, reviewer, random.random())
        for paper, reviewer in itertools.product(papers, reviewers)
    ]

    minimums = [1, 1, 1]
    maximums = [1, 1, 1]
    demands = [1, 1, 1]

    test_matcher = Matcher(
        {
            "reviewers": reviewers,
            "papers": papers,
            "scores_by_type": {"affinity": {"edges": scores}},
            "weight_by_type": {"affinity": 1},
            "minimums": minimums,
            "maximums": maximums,
            "demands": demands,
            "num_alternates": 1,
        },
        solver_class="MinMax",
    )

    test_matcher.run()

    assert test_matcher.solution.any()
    assert test_matcher.assignments
    assert test_matcher.alternates


def test_matcher_basic_fairflow():
    reviewers = ["reviewer1", "reviewer2", "reviewer3"]
    papers = ["paper1", "paper2", "paper3"]

    scores = [
        (paper, reviewer, random.random())
        for paper, reviewer in itertools.product(papers, reviewers)
    ]

    minimums = [1, 1, 1]
    maximums = [1, 1, 1]
    demands = [1, 1, 1]

    test_matcher = Matcher(
        {
            "reviewers": reviewers,
            "papers": papers,
            "scores_by_type": {"affinity": {"edges": scores}},
            "weight_by_type": {"affinity": 1},
            "minimums": minimums,
            "maximums": maximums,
            "demands": demands,
            "num_alternates": 1,
        },
        solver_class="FairFlow",
    )

    test_matcher.run()

    assert test_matcher.solution.any()
    assert test_matcher.assignments
    assert test_matcher.alternates


def test_matcher_minmax_fixed_input():
    reviewers = ["reviewer1", "reviewer2", "reviewer3"]
    papers = ["paper1", "paper2", "paper3"]

    scores = [
        ("paper1", "reviewer1", 1),
        ("paper1", "reviewer2", 0),
        ("paper1", "reviewer3", 0.25),
        ("paper2", "reviewer1", 1),
        ("paper2", "reviewer2", 0),
        ("paper2", "reviewer3", 0.25),
        ("paper3", "reviewer1", 1),
        ("paper3", "reviewer2", 0.2),
        ("paper3", "reviewer3", 0.5),
    ]

    minimums = [1, 1, 1]
    maximums = [1, 1, 1]
    demands = [1, 1, 1]

    test_minmax_matcher = Matcher(
        {
            "reviewers": reviewers,
            "papers": papers,
            "scores_by_type": {"affinity": {"edges": scores}},
            "weight_by_type": {"affinity": 1},
            "minimums": minimums,
            "maximums": maximums,
            "demands": demands,
            "num_alternates": 1,
        },
        solver_class="MinMax",
    )

    test_minmax_matcher.run()

    assert len(test_minmax_matcher.solution) == 3
    assert len(test_minmax_matcher.solution[0]) == 3
    assert (
        nptest.assert_array_equal(
            test_minmax_matcher.solution,
            [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]],
        )
        is None
    )
    assert test_minmax_matcher.assignments
    assert test_minmax_matcher.alternates


def test_matcher_fairflow_fixed_input():
    reviewers = ["reviewer1", "reviewer2", "reviewer3"]
    papers = ["paper1", "paper2", "paper3"]

    scores = [
        ("paper1", "reviewer1", 1),
        ("paper1", "reviewer2", 0),
        ("paper1", "reviewer3", 0.25),
        ("paper2", "reviewer1", 1),
        ("paper2", "reviewer2", 0),
        ("paper2", "reviewer3", 0.25),
        ("paper3", "reviewer1", 1),
        ("paper3", "reviewer2", 0.2),
        ("paper3", "reviewer3", 0.5),
    ]

    minimums = [1, 1, 1]
    maximums = [1, 1, 1]
    demands = [1, 1, 1]

    test_fairflow_matcher = Matcher(
        {
            "reviewers": reviewers,
            "papers": papers,
            "scores_by_type": {"affinity": {"edges": scores}},
            "weight_by_type": {"affinity": 1},
            "minimums": minimums,
            "maximums": maximums,
            "demands": demands,
            "num_alternates": 1,
        },
        solver_class="FairFlow",
    )

    test_fairflow_matcher.run()

    assert len(test_fairflow_matcher.solution) == 3
    assert len(test_fairflow_matcher.solution[0]) == 3
    assert (
        nptest.assert_array_equal(
            test_fairflow_matcher.solution,
            [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        )
        is None
    )
    assert test_fairflow_matcher.assignments
    assert test_fairflow_matcher.alternates
