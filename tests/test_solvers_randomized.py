import pytest
from collections import namedtuple
import numpy as np
from matcher.solvers import SolverException, RandomizedSolver

cost_scale = 1000


class encoder:
    def __init__(self, cost, constraint, prob_limit):
        self.cost_matrix = cost * cost_scale
        self.constraint_matrix = constraint
        self.prob_limit_matrix = prob_limit


def check_sampled_solution(solver):
    """Performs basic checks on the validity of a sampled assignment"""
    pap_loads = np.sum(solver.flow_matrix, axis=1)
    rev_loads = np.sum(solver.flow_matrix, axis=0)
    assert np.all(
        np.logical_or(solver.flow_matrix == 0, solver.flow_matrix == 1)
    ), "Sampled assignments should be integral"
    assert np.all(pap_loads == np.array(solver.demands)) and np.all(
        np.logical_and(
            rev_loads <= np.array(solver.maximums),
            rev_loads >= np.array(solver.minimums),
        )
    ), "Sampled assignment should be in legal polytope"
    assert np.all(
        np.where(solver.constraint_matrix == -1, solver.flow_matrix == 0, True)
    ), "Sampled assignment should obey constraint matrix"


def check_test_solution(solver, T=1000, tol=1e-1):
    """
    Takes several samples and performs basic checks on the correctness of the fractional assignment
    and the sampled assignments. T = number of samples, tol = tolerance for the mean matrix
    Note that this function is random and could potentially cause false test failures in very rare cases.
    """
    solver.solve()
    assert solver.solved, "Problem should be solvable"

    pap_loads = np.sum(solver.fractional_assignment_matrix, axis=1)
    rev_loads = np.sum(solver.fractional_assignment_matrix, axis=0)
    assert (
        np.all(pap_loads == np.array(solver.demands))
        and np.all(
            np.logical_and(
                rev_loads <= np.array(solver.maximums),
                rev_loads >= np.array(solver.minimums),
            )
        )
        and np.all(
            np.logical_and(
                solver.fractional_assignment_matrix <= 1,
                solver.fractional_assignment_matrix >= 0,
            )
        )
    ), "Fractional assignment should be in legal polytope"
    assert np.all(
        np.where(
            solver.constraint_matrix == -1,
            solver.fractional_assignment_matrix == 0,
            True,
        )
    ) and np.all(
        np.where(
            solver.constraint_matrix == 1,
            solver.fractional_assignment_matrix == solver.prob_limit_matrix,
            True,
        )
    ), "Fractional assignment should obey constraint matrix"

    for i in range(T):
        if i == 0:
            mean_matrix = solver.flow_matrix
        else:
            solver.sample_assignment()
            mean_matrix += solver.flow_matrix
        check_sampled_solution(solver)
    mean_matrix /= T

    assert np.all(
        np.abs(mean_matrix - solver.fractional_assignment_matrix) < tol
    ), "Mean sampled solution should be close to fractional assignment"


def test_basic():
    """Simple test for basic functionality"""
    S = np.transpose(np.array([[1, 0.1], [1, 1], [0.3, 0.6], [0.5, 0.8]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.75)
    solver = RandomizedSolver(
        [0, 0, 0, 0], [1, 1, 1, 1], [2, 2], encoder(-S, M, Q)
    )

    check_test_solution(solver)
    # verify correct solution
    solution = np.transpose(
        np.array([[0.75, 0.25], [0.75, 0.25], [0.25, 0.75], [0.25, 0.75]])
    )
    assert np.all(
        solver.fractional_assignment_matrix == solution
    ), "Fractional assignment should be correct"


def test_varied_limits():
    """Test with varying probability limits"""
    S = np.transpose(np.array([[1, 0.1], [1, 1], [0.3, 0.6], [0.5, 0.8]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.75)
    Q[0, 0] = 0.5
    Q[1, 2] = 0.25
    Q[0, 1] = 0.5
    Q[0, 3] = 1
    solver = RandomizedSolver(
        [0, 0, 0, 0], [1, 1, 1, 1], [2, 2], encoder(-S, M, Q)
    )

    check_test_solution(solver)

    solution = np.transpose(
        np.array([[0.5, 0.5], [0.5, 0.5], [0.75, 0.25], [0.25, 0.75]])
    )
    assert np.all(
        solver.fractional_assignment_matrix == solution
    ), "Fractional assignment should be correct"


def test_bad_limits():
    """Test for error-checking the probability limits"""
    S = np.transpose(np.array([[1, 0.1], [1, 1], [0.3, 0.6], [0.5, 0.8]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.75)

    Q[1, 1] = -1
    try:
        solver = RandomizedSolver(
            [0, 0, 0, 0], [1, 1, 1, 1], [2, 2], encoder(-S, M, Q)
        )
        assert False  # should throw
    except SolverException:
        pass

    Q[1, 1] = 1.5
    try:
        solver = RandomizedSolver(
            [0, 0, 0, 0], [1, 1, 1, 1], [2, 2], encoder(-S, M, Q)
        )
        assert False  # should throw
    except SolverException:
        pass


def test_different_supply_demand():
    """Test for custom supplies and demands"""
    S = np.transpose(
        np.array(
            [[1, 0.1, 0.5], [1, 1, 0.5], [0.3, 0.6, 0.5], [0.5, 0.8, 0.5]]
        )
    )
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.75)

    solver = RandomizedSolver(
        [0, 1, 1, 0], [1, 3, 2, 1], [3, 2, 1], encoder(-S, M, Q)
    )
    check_test_solution(solver)


def test_reviewer_minimums():
    """Ensure that reviewer minimums are maintained even when it increases cost"""
    S = np.transpose(np.array([[0, 0, 0], [1.0, 1.0, 1.0]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 1.0)

    solver = RandomizedSolver([1, 1], [3, 3], [1, 1, 1], encoder(-S, M, Q))
    solver.solve()
    check_sampled_solution(solver)


def test_impossible_constraints():
    """Test when problem cannot be solved due to probability constraints"""
    S = np.transpose(
        np.array(
            [[1, 0.1, 0.5], [1, 1, 0.5], [0.3, 0.6, 0.5], [0.5, 0.8, 0.5]]
        )
    )
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.75)
    Q[0, :] = 0  # no probability on first paper

    solver = RandomizedSolver(
        [0, 0, 0, 0], [3, 3, 3, 3], [2, 2, 2], encoder(-S, M, Q)
    )
    solver.solve()
    assert not solver.solved

    Q = np.full(np.shape(S), 0.75)
    Q[:, 0] = 0  # no probability on first reviewer
    solver = RandomizedSolver(
        [0, 0, 0, 0], [3, 3, 3, 3], [2, 2, 2], encoder(-S, M, Q)
    )
    solver.solve()
    assert solver.solved  # ok if minimum is 0
    solver = RandomizedSolver(
        [1, 1, 1, 1], [3, 3, 3, 3], [2, 2, 2], encoder(-S, M, Q)
    )
    solver.solve()
    assert not solver.solved  # not if minimum is 1


def test_fractional_reviewer_load():
    """Test that sampling works correctly if some reviewer loads are fractional"""
    S = np.ones((3, 3))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.4)

    solver = RandomizedSolver(
        [0, 0, 0], [2, 2, 2], [1, 1, 1], encoder(-S, M, Q)
    )
    solver.solve()

    # all assignments equally valid, so can change fractional assignment
    F = np.transpose(
        np.array([[0.4, 0.4, 0.4], [0.4, 0.4, 0.4], [0.2, 0.2, 0.2]])
    )
    solver.fractional_assignment_matrix = F
    for _ in range(100):
        solver.sample_assignment()
        check_sampled_solution(solver)


def test_low_reviewer_load():
    """Test that sampling works correctly if all reviewer loads are below one"""
    S = np.ones((3, 4))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.3)  # each reviewer has load 0.9 at most

    solver = RandomizedSolver(
        [0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1], encoder(-S, M, Q)
    )
    solver.solve()

    for _ in range(100):
        solver.sample_assignment()
        check_sampled_solution(solver)


def test_solution_optimal_no_limit():
    """Test that the correct optimal solution is found without probability limits"""
    S = np.transpose(
        np.array([[0, 0.4, 0.7], [0.3, 0.6, 0.5], [0.5, 0.8, 0.5]])
    )
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 1.0)

    solver = RandomizedSolver(
        [0, 0, 0], [2, 2, 2], [2, 2, 2], encoder(-S, M, Q)
    )
    solution = np.transpose(np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]]))
    solver.solve()

    assert np.all(solver.fractional_assignment_matrix == solution) and np.all(
        solver.flow_matrix == solution
    )
    assert solver.expected_cost == (cost_scale * -3.2) and solver.cost == (
        cost_scale * -3.2
    )
    solver.sample_assignment()  # should not change since assignment is deterministic
    assert np.all(solver.fractional_assignment_matrix == solution) and np.all(
        solver.flow_matrix == solution
    )
    assert solver.expected_cost == (cost_scale * -3.2) and solver.cost == (
        cost_scale * -3.2
    )


def test_constraints():
    """Ensure constraint matrix is respected"""
    S = np.transpose(
        np.array(
            [[1, 0.1, 0.5], [1, 1, 0.5], [0.3, 0.6, 0.5], [0.5, 0.8, 0.5]]
        )
    )
    M = np.transpose(np.array([[-1, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, 1]]))
    Q = np.full(np.shape(S), 0.75)

    solver = RandomizedSolver(
        [0, 0, 0, 0], [3, 3, 3, 3], [2, 2, 2], encoder(-S, M, Q)
    )
    check_test_solution(solver)


def test_large():
    """Ensure things still work in a larger case"""
    p = 20
    r = 60
    S = np.random.random((p, r))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.5)
    solver = RandomizedSolver([1] * r, [3] * r, [3] * p, encoder(-S, M, Q))
    check_test_solution(solver, 100, 0.2)


def test_alternates():
    """Test that alternates are selected correctly"""

    # probability limits 1 case
    S = np.transpose(np.array([[0, 0.3, 1], [1, 0.5, 0.4], [0.4, 1, 0.3]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 1.0)

    solver = RandomizedSolver(
        [0, 0, 0], [1, 1, 1], [1, 1, 1], encoder(-S, M, Q)
    )
    solution = np.transpose(np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]]))
    solver.solve()

    alternates = {0: [2, 0], 1: [1, 0], 2: [1, 2]}

    alt_probs = np.ones((3, 3)) - solution

    answer = solver.get_alternates(2)
    assert np.all(solver.fractional_assignment_matrix == solution)
    assert np.all(solver.alternate_probability_matrix == alt_probs)
    assert np.all(answer == alternates)

    # test with lower probability limits
    Q = np.full(np.shape(S), 0.7)
    solver = RandomizedSolver(
        [0, 0, 0], [1, 1, 1], [1, 1, 1], encoder(-S, M, Q)
    )
    solution = np.transpose(
        np.array([[0, 0.3, 0.7], [0.7, 0, 0.3], [0.3, 0.7, 0]])
    )
    alt_probs = np.transpose(
        np.array([[0.7, 4 / 7, 0], [0, 0.7, 4 / 7], [4 / 7, 0, 0.7]])
    )
    solver.solve()
    assert np.all(np.isclose(solution, solver.fractional_assignment_matrix))
    assert np.all(np.isclose(alt_probs, solver.alternate_probability_matrix))


def test_opt_fraction():
    """Test that fraction of opt is calculated correctly"""
    S = np.eye(5)
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 0.5)
    solver = RandomizedSolver(
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        encoder(-S, M, Q),
        True,  # allow zero score assignment
    )

    solver.solve()
    assert solver.solved and solver.opt_solved
    assert solver.expected_cost == (cost_scale * -2.5)
    assert solver.opt_cost == (cost_scale * -5)
    assert solver.get_fraction_of_opt() == 0.5

    S = np.eye(5)
    for i in range(1, 5):
        S[i - 1, i] = 1
    S[4, 0] = 1
    solver = RandomizedSolver(
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        encoder(-S, M, Q),
        True,  # allow zero score assignment
    )

    solver.solve()
    assert solver.solved and solver.opt_solved
    assert solver.expected_cost == (cost_scale * -5)
    assert solver.opt_cost == (cost_scale * -5)
    assert solver.get_fraction_of_opt() == 1

    Q = np.full(np.shape(S), 0.3)
    solver = RandomizedSolver(
        [0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        encoder(-S, M, Q),
        True,  # allow zero score assignment
    )

    solver.solve()
    assert solver.solved and solver.opt_solved
    assert solver.expected_cost == (cost_scale * -3)
    assert solver.opt_cost == (cost_scale * -5)
    assert solver.get_fraction_of_opt() == 0.6


def test_identical_costs():
    """Test that LP is integral when all costs identical"""
    S = np.transpose(np.array([[1.0, 1], [1, 1], [1, 1], [1, 1]]))
    M = np.zeros(np.shape(S))
    Q = np.full(np.shape(S), 1.0)
    solver = RandomizedSolver(
        [0, 0, 0, 0], [1, 1, 1, 1], [2, 2], encoder(-S, M, Q)
    )
    for _ in range(1000):
        check_test_solution(solver, T=1)
