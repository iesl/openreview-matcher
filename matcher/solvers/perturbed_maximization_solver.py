"""
A paper-reviewer assignment solver that aims to trade off between the total
affinity score and the randomness of the assignment. The solver is based on
the algorithm described in Xu et al 2023.

The solver relies on the Gurobi optimizer to solve convex quadratic programs
that arise in the assignment problem, and the CFFI library to interface with
a sampling program written in C.
"""

import logging
import numpy as np
import gurobipy as gp
from cffi import FFI
from .core import SolverException
from .bvn_extension import run_bvn
from .minmax_solver import MinMaxSolver

class PerturbedMaximizationSolver:
    def __init__(
        self,
        minimums,
        maximums,
        demands,
        encoder,
        allow_zero_score_assignments=False,
        logger=logging.getLogger(__name__),
    ):
        """
        Initialize the solver with the given encoder and constraints.
        """
        
        self.logger = logger
        self.logger.debug("[PerturbedMaximization]: Initializing ...")

        # Store the inputs
        self.num_paps, self.num_revs = encoder.cost_matrix.shape
        self.allow_zero_score_assignments = allow_zero_score_assignments
        self.encoder = encoder

        self.minimums = minimums
        self.maximums = maximums
        self.demands = demands
        self.cost_matrix = encoder.cost_matrix
        self.constraint_matrix = encoder.constraint_matrix
        self.prob_limit_matrix = encoder.prob_limit_matrix
        self.perturbation = encoder.perturbation
        self.bad_match_thresholds = encoder.bad_match_thresholds

        # Reduce the minimums of reviewers with no known affinity with any paper to 0
        if not self.allow_zero_score_assignments:
            self.constraint_matrix[
                np.where(self.cost_matrix == 0)
            ] = -1
            bad_affinity_reviewers = np.where(
                np.all(
                    (self.cost_matrix * (self.constraint_matrix >= 0)) == 0,
                    axis=0,
                )
            )[0]
            self.logger.debug(
                "[PerturbedMaximization]: Setting minimum load for {} reviewers to 0 "
                "because they do not have known affinity with any paper".format(
                    len(bad_affinity_reviewers)
                )
            )
            for rev_id in bad_affinity_reviewers:
                self.minimums[rev_id] = 0

        # Check input validity
        self._check_inputs()

        # Initialize solver variables
        self.solved = False
        self.fractional_assignment_matrix = None
        self.fractional_assignment_cost = None
        self.sampled_assignment_matrix = None
        self.sampled_assignment_cost = None
        self.alternate_probability_matrix = None

        # Compute the deterministic max-affinity assignment ingoring probability limits
        #     This is used to compute the fraction of the optimal score achieved 
        #     by the randomized assignment. We use the Gurobi optimizer to solve 
        #     the deterministic assignment problem as a linear program.
        self.logger.debug("[PerturbedMaximization]: Computing the optimal "
                          "deterministic assignment ...")
        solver = gp.Model()
        solver.setParam('OutputFlag', 0)
        # Initialize assignment matrix and objective function
        objective  = 0.0
        assignment = [[0.0 for j in range(self.num_revs)] for i in range(self.num_paps)]
        for i in range(self.num_paps):
            for j in range(self.num_revs):
                if self.constraint_matrix[i][j] == -1 or self.cost_matrix[i][j] > 0:
                    x = solver.addVar(lb=0, ub=0, name=f"{i} {j}")
                elif self.constraint_matrix[i][j] == 1:
                    x = solver.addVar(lb=1, ub=1, name=f"{i} {j}")
                else:
                    x = solver.addVar(lb=0, ub=1, name=f"{i} {j}")
                assignment[i][j] = x
                objective += x * self.cost_matrix[i][j]
        solver.setObjective(objective, gp.GRB.MINIMIZE)
        # Add constraints
        for i in range(self.num_paps):
            assigned = 0.0
            for j in range(self.num_revs):
                assigned += assignment[i][j]
            solver.addConstr(assigned == self.demands[i])
        for j in range(self.num_revs):
            load = 0.0
            for i in range(self.num_paps):
                load += assignment[i][j]
            solver.addConstr(load >= self.minimums[j])
            solver.addConstr(load <= self.maximums[j])
        # Run the Gurobi solver
        solver.optimize()
        if solver.status != gp.GRB.OPTIMAL:
            self.deterministic_assignment_solved = False
            self.logger.debug(
                "[PerturbedMaximization]: ERROR: Deterministic assignment infeasible"
            )
            raise SolverException("Deterministic assignment infeasible")
        # Compute properties of the deterministic assignment
        self.deterministic_assignment_solved = True
        self.deterministic_assignment_matrix = np.array([
            [assignment[i][j].x for j in range(self.num_revs)] for i in range(self.num_paps)
        ])
        self.deterministic_assignment_cost = self._compute_expected_cost(
            self.deterministic_assignment_matrix
        )
        self.logger.debug("[PerturbedMaximization]: Finished computing the optimal "
                          "deterministic assignment, total affinity score "
                          f"{-self.deterministic_assignment_cost:.6f}")

        # Compute the max-affinity assignment subject only to probability limits
        #     This is used to compute constraints on the number of bad matches or
        #     insufficiently good matches in the randomized assignment. We require
        #     that the fractional assignment with perturbation does not have more
        #     bad matches than the fractional assignment without perturbation.
        if len(self.bad_match_thresholds) != 0:
            self.logger.debug("[PerturbedMaximization]: Computing the fractional "
                              "assignment without perturbation ...")
            solver = gp.Model()
            solver.setParam('OutputFlag', 0)
            # Initialize assignment matrix and objective function
            objective  = 0.0
            assignment = [
                [0.0 for j in range(self.num_revs)] for i in range(self.num_paps)
            ]
            for i in range(self.num_paps):
                for j in range(self.num_revs):
                    if self.constraint_matrix[i][j] == -1 or self.cost_matrix[i][j] > 0:
                        x = solver.addVar(lb=0, ub=0, name=f"{i} {j}")
                    elif self.constraint_matrix[i][j] == 1:
                        x = solver.addVar(lb=1, ub=1, name=f"{i} {j}")
                    else:
                        x = solver.addVar(lb=0, ub=self.prob_limit_matrix[i][j], 
                                          name=f"{i} {j}")
                    assignment[i][j] = x
                    objective += x * self.cost_matrix[i][j]
            solver.setObjective(objective, gp.GRB.MINIMIZE)
            # Add constraints
            for i in range(self.num_paps):
                assigned = 0.0
                for j in range(self.num_revs):
                    assigned += assignment[i][j]
                solver.addConstr(assigned == self.demands[i])
            for j in range(self.num_revs):
                load = 0.0
                for i in range(self.num_paps):
                    load += assignment[i][j]
                solver.addConstr(load >= self.minimums[j])
                solver.addConstr(load <= self.maximums[j])
            # Run the Gurobi solver
            solver.optimize()
            if solver.status != gp.GRB.OPTIMAL:
                self.fractional_assignment_solved = False
                self.logger.debug(
                    "[PerturbedMaximization]: ERROR: Fractional assignment without "
                    "perturbation infeasible"
                )
                raise SolverException(
                    "Fractional assignment without perturbation infeasible"
                )
            self.no_perturbation_assignment_matrix = np.array([
                [assignment[i][j].x for j in range(self.num_revs)] for i in range(self.num_paps)
            ])
            self.logger.debug("[PerturbedMaximization]: Finished computing the "
                              "fractional assignment without perturbation")
                          
        self.logger.debug("[PerturbedMaximization]: Finished initializing")

    def _check_inputs(self):
        """
        Check the validity of the input parameters.
        """

        self.logger.debug("[PerturbedMaximization]: Checking inputs ...")

        # Cost matrix
        if not isinstance(self.cost_matrix, np.ndarray):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Cost matrix must be of type numpy.ndarray"
            )
        if not np.shape(self.cost_matrix) == (self.num_paps, self.num_revs):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Cost matrix must be in shape [#papers, #reviewers]"
            )

        # Constraint matrix
        if not isinstance(self.constraint_matrix, np.ndarray):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Constraint matrix must be of type numpy.ndarray"
            )
        if not np.shape(self.constraint_matrix) == (self.num_paps, self.num_revs):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Constraint matrix must be in shape [#papers, #reviewers]"
            )
        if not np.all(
            np.logical_or(
                np.logical_or(
                    self.constraint_matrix == 0,
                    self.constraint_matrix == 1
                ),
                self.constraint_matrix == -1
            )
        ):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Values in the constraint matrix must be in {-1, 0, 1}"
            )

        # Probability limit matrix
        if not isinstance(self.prob_limit_matrix, np.ndarray):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Probability limit matrix must be of type numpy.ndarray"
            )
        if not np.shape(self.prob_limit_matrix) == (self.num_paps, self.num_revs):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Probability limit matrix must be in shape [#papers, #reviewers]"
            )
        if not np.all(np.logical_and(
            self.prob_limit_matrix >= 0,
            self.prob_limit_matrix <= 1
        )):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Values in the probability limit matrix must be in [0, 1]"
            )

        # Minimums
        if not isinstance(self.minimums, list):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Minimums must be of type numpy.ndarray"
            )
        if not len(self.minimums) == self.num_revs:
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Minimums must be in shape [#reviewers]"
            )
        if not np.all(np.array(self.minimums) >= 0):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Values in the minimums must be non-negative"
            )

        # Maximums
        if not isinstance(self.maximums, list):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Maximums must be of type numpy.ndarray"
            )
        if not len(self.maximums) == self.num_revs:
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Maximums must be in shape [#reviewers]"
            )
        if not np.all(np.array(self.maximums) >= np.array(self.minimums)):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Values in the maximums must be greater than or equal to the corresponding minimums"
            )

        # Demands
        if not isinstance(self.demands, list):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Demands must be of type numpy.ndarray"
            )
        if not len(self.demands) == self.num_paps:
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Demands must be in shape [#papers]"
            )
        if not np.all(np.array(self.demands) >= 0):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Values in the demands must be non-negative"
            )

        # Perturbation
        if not isinstance(self.perturbation, (float, int)):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Perturbation must be a number"
            )
        if not self.perturbation >= 0:
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Perturbation must be non-negative"
            )
        
        # Bad match thresholds
        if not isinstance(self.bad_match_thresholds, list):
            self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
            raise SolverException(
                "Bad match thresholds must be of type list"
            )
        for threshold in self.bad_match_thresholds:
            if not isinstance(threshold, (float, int)):
                self.logger.debug("[PerturbedMaximization]: ERROR: Invaild input")
                raise SolverException(
                    "Bad match thresholds must be a list of numbers"
                )

        # OR Validation
        self.logger.debug("Checking if demand is in range")

        min_supply = sum(self.minimums)
        max_supply = sum(self.maximums)
        demand = sum(self.demands)

        self.logger.debug(
            "Total demand is ({}), min review supply is ({}), and max review supply is ({})".format(
                demand, min_supply, max_supply
            )
        )

        if demand > max_supply or demand < min_supply:
            raise SolverException(
                "Review demand ({}) must be between the min review supply is ({}) and max review supply is ({}).".format(
                    demand, min_supply, max_supply
                ) + " Try (1) decreasing min papers (2) increasing max papers or (3) finding more reviewers"
            )

        self.logger.debug("[PerturbedMaximization]: Finished checking inputs")

    def sample_assignment(self):
        """
        Sample an assignment from the fractional assignment matrix.
        """

        self.logger.debug("[PerturbedMaximization]: Sampling assignment ...")
        
        # The fractional solver must be solved before sampling
        if not self.solved:
            self.logger.debug(
                "[PerturbedMaximization]: ERROR: Fractional solver not solved yet"
            )
            raise SolverException("Fractional solver not solved yet")
    
        # Round the fractional assignment matrix to integers to a certain precision
        # in order to use the sampling program in C. See also the RandomizedSolver.
        self.precision = 1000000
        self.rounded_assignment_matrix = np.zeros(
            (self.num_paps, self.num_revs), dtype=int
        )
        for i in range(self.num_paps):
            for j in range(self.num_revs):
                self.rounded_assignment_matrix[i][j] = np.round(
                    self.fractional_assignment_matrix[i][j] * self.precision
                )

        # Construct CFFI interface to use the sampling extension in C
        ffi = FFI()
        F = self.rounded_assignment_matrix.flatten()
        Fbuf = ffi.new("int[]", self.num_paps * self.num_revs)
        for i in range(F.size):
            Fbuf[i] = F[i]
        Sbuf = ffi.new("int[]", self.num_revs)
        for i in range(self.num_revs):
            Sbuf[i] = 1
        run_bvn(Fbuf, Sbuf, self.num_paps, self.num_revs, self.precision)

        # Obtain the sampled assignment matrix and compute properties
        self.sampled_assignment_matrix = np.zeros((self.num_paps, self.num_revs))
        for i in range(F.size):
            coords = np.unravel_index(i, (self.num_paps, self.num_revs))
            self.sampled_assignment_matrix[coords] = Fbuf[i]
        self.sampled_assignment_cost = self._compute_expected_cost(self.sampled_assignment_matrix)
        sampled_cost_ratio = 1.0
        if self.deterministic_assignment_cost != 0:
            sampled_cost_ratio = self.sampled_assignment_cost / self.deterministic_assignment_cost

        # Review the constraints
        pap_loads = np.sum(self.sampled_assignment_matrix, axis=1)
        for i in range(self.num_paps):
            if pap_loads[i] != self.demands[i]:
                self.logger.debug(f"[PerturbedMaximization]: Warning: Paper {i} has" 
                                  f"load {pap_loads[i]} but demand {self.demands[i]}")
        rev_loads = np.sum(self.sampled_assignment_matrix, axis=0)
        for j in range(self.num_revs):
            if rev_loads[j] < self.minimums[j] or rev_loads[j] > self.maximums[j]:
                self.logger.debug(f"[PerturbedMaximization]: Warning: Reviewer {j} has " 
                                  f"load {rev_loads[j]} but limits "
                                  f"[{self.minimums[j]}, {self.maximums[j]}]")
                                  
        self.logger.debug("[PerturbedMaximization]: Finished sampling assignment with "
                          f"score {-self.sampled_assignment_cost:.6f}, "
                          f"{sampled_cost_ratio:.2%} of the deterministic score")
    
    def _compute_expected_cost(self, assignment):
        expected_cost = 0.0
        for i in range(self.num_paps):
            for j in range(self.num_revs):
                expected_cost += assignment[i][j] * self.cost_matrix[i][j]
        return expected_cost

    def solve(self):
        """
        Solve the assignment problem with probability constraints and perturbation.
        This is the QuadraticPM algorithm from Xu et al 2023, where the perturbation
        function used is f(x) = x - p * x^2 with p = the perturbation variable.
        """

        self.logger.debug(
            "[PerturbedMaximization]: Solving the fractional assignment ..."
        )

        # Solve the fractional assignment problem using Gurobi
        #    The objective function is total preturbed score of each paper-reviewer
        #    pair. Let the marginal probability of reviewer j being assigned to paper
        #    i be x_ij. The objective function is sum_{i,j} c_ij * (x_ij - p * x_ij^2).
        #    The convex quadratic program is solved using Gurobi.
        solver = gp.Model()
        solver.setParam('OutputFlag', 0)
        # Initialize assignment matrix and objective function
        objective  = 0.0
        assignment = [[0.0 for j in range(self.num_revs)] for i in range(self.num_paps)]
        for i in range(self.num_paps):
            for j in range(self.num_revs):
                if self.constraint_matrix[i][j] == -1 or self.cost_matrix[i][j] > 0:
                    x = solver.addVar(lb=0, ub=0, name=f"{i} {j}")
                elif self.constraint_matrix[i][j] == 1:
                    x = solver.addVar(lb=1, ub=1, name=f"{i} {j}")
                else:
                    x = solver.addVar(lb=0, ub=self.prob_limit_matrix[i][j], 
                                      name=f"{i} {j}")
                assignment[i][j] = x
                objective += (x - self.perturbation * x * x) * self.cost_matrix[i][j]
        solver.setObjective(objective, gp.GRB.MINIMIZE)
        # Add constraints
        for i in range(self.num_paps):
            assigned = 0.0
            for j in range(self.num_revs):
                assigned += assignment[i][j]
            solver.addConstr(assigned == self.demands[i])
        for j in range(self.num_revs):
            load = 0.0
            for i in range(self.num_paps):
                load += assignment[i][j]
            solver.addConstr(load >= self.minimums[j])
            solver.addConstr(load <= self.maximums[j])
        for threshold in self.bad_match_thresholds:
            no_perturbation_bad_matches = np.sum(
                self.no_perturbation_assignment_matrix * (self.cost_matrix > threshold)
            )
            bad_matches = 0.0
            for i in range(self.num_paps):
                for j in range(self.num_revs):
                    bad_matches += assignment[i][j] * (self.cost_matrix[i][j] > threshold)
            solver.addConstr(bad_matches <= no_perturbation_bad_matches)
        # Run the Gurobi solver
        solver.optimize()
        if solver.status != gp.GRB.OPTIMAL:
            self.solved = False
            self.logger.debug("[PerturbedMaximization]: Gurobi solver failed")
            return None
        # Compute properties of the fractional assignment
        self.solved = True
        self.fractional_assignment_matrix = np.array([
            [assignment[i][j].x for j in range(self.num_revs)] for i in range(self.num_paps)
        ])
        self.fractional_assignment_cost = self._compute_expected_cost(self.fractional_assignment_matrix)
        self.logger.debug(
            "[PerturbedMaximization]: Finished solving the fractional assignment "
            f"with score {-self.fractional_assignment_cost:.6f}, "
            f"{self.get_fraction_of_opt():.2%} of the deterministic score"
        )

        # Sample the assignment and return the sampled assignment matrix
        self.sample_assignment()
        return self.sampled_assignment_matrix

    def get_alternates(self, num_alternates):
        """
        Get a list of alternates for each paper.
        """

        self.logger.debug("[PerturbedMaximization]: Getting alternates ...")
        
        # The fractional solver must be solved before getting alternates
        if not self.solved:
            self.logger.debug(
                "[PerturbedMaximization]: ERROR: Fractional solver not solved yet"
            )
            raise SolverException("Fractional solver not solved yet")

        # Compute the probability of each reviewer being an
        # alternate, given the result of the sampling
        self.alternate_probability_matrix = np.divide(
            self.prob_limit_matrix - self.fractional_assignment_matrix,
            1 - self.fractional_assignment_matrix,
            out=(np.zeros_like(self.prob_limit_matrix)),
            where=(self.fractional_assignment_matrix < 1),
        )

        # Get the alternates for each paper and return them
        rng = np.random.default_rng()
        alternates_by_index = {}
        for i in range(self.num_paps):
            unassigned = []
            for j in range(self.num_revs):
                # only allow j as an alternate with limited probability
                if (
                    self.sampled_assignment_matrix[i, j] == 0
                    and rng.random() < self.alternate_probability_matrix[i, j]
                ):
                    unassigned.append((self.cost_matrix[i, j], j))
            unassigned.sort()
            alternates_by_index[i] = [
                entry[1] for entry in unassigned[:num_alternates]
            ]
        self.logger.debug("[PerturbedMaximization]: Finished getting alternates")
        return alternates_by_index

    def get_fraction_of_opt(self):
        """
        Return the fraction of the best affinity score achieved by the randomized assignment (in expectation).
        """
        self.logger.debug("[PerturbedMaximization]: Getting fraction of opt ...")
        
        if not (self.solved and self.deterministic_assignment_solved):
            self.logger.debug("[PerturbedMaximization]: ERROR: Fractional solver not solved yet")
            raise SolverException("Fractional solver not solved yet")
        return self.fractional_assignment_cost / self.deterministic_assignment_cost if self.deterministic_assignment_cost != 0 else 1
