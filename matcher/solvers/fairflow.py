from collections import defaultdict
from ortools.graph import pywrapgraph
import numpy as np
import uuid
import time
from .core import SolverException
import logging


class FairFlow(object):
    """Approximate makespan matching via flow network (with lower bounds).

    Approximately solve the reviewer assignment problem with makespan
    constraint. Based on the algorithm introduced in Gairing et. al 2004 and
    Gairing et. al. 2007.  Our adaptation works as follows.  After we have a
    matching, construct three groups of papers.  The first group are all papers
    with scores > makespan value, the second group are all papers whose
    papers scores are between the makespan and the makespan - maxaffinity, the
    final group are the papers whose paper scores are less than makespan -
    maxaffinity.  For each paper in the last group, we'll unassign the
    reviewer with the lowest score. Then, we'll construct a new flow network
    from the papers in the first group as sources through reviewers assigned to
    those paper and terminating in the papers in the last group. Each sink will
    accept a single new assignment.  Once this assignment is made.  We'll
    construct another flow network of all available reviewers to the papers that
    do not have enough reviewers and solve the flow problem again.  Then we'll
    have a feasible solution. We can continue to iterate this process until
    either: there are no papers in the first group, there are no papers in the
    third group, or running the procedure does not change the sum total score of
    the matching.
    """

    def __init__(
        self,
        minimums,
        maximums,
        demands,
        encoder,
        allow_zero_score_assignments=False,
        solution=None,
        logger=logging.getLogger(__name__),
    ):
        """
        Initialize a makespan flow matcher

        :param minimums: a list of integers specifying the minimum number of papers for each reviewer.
        :param maximums: a list of integers specifying the maximum number of papers for each reviewer.
        :param demands: a list of integers specifying the number of reviews required per paper.
        :param encoder: an Encoder class object used to get affinity and constraint matrices.
        :param allow_zero_score_assignments: bool to allow pairs with zero affinity in the solution.
            unknown matching scores default to 0. set to True to allow zero (unknown) affinity in solution.
        :param solution: a matrix of assignments (same shape as encoder.affinity_matrix)

        :return: initialized makespan matcher.
        """
        self.logger = logger
        self.allow_zero_score_assignments = allow_zero_score_assignments
        self.logger.debug("Init FairFlow")
        self.constraint_matrix = encoder.constraint_matrix
        affinity_matrix = encoder.aggregate_score_matrix.transpose()

        self.maximums = maximums
        self.minimums = minimums
        self.demands = demands
        # make sure that all weights are positive:
        self.affinity_matrix = affinity_matrix.copy()
        if not self.affinity_matrix.any():
            self.affinity_matrix = np.random.rand(*affinity_matrix.shape)

        self.orig_affinities = self.affinity_matrix.copy()

        self.num_reviewers = np.size(self.affinity_matrix, axis=0)
        self.num_papers = np.size(self.affinity_matrix, axis=1)

        if not self.allow_zero_score_assignments:
            # Find reviewers with no non-zero affinity edges after constraints are applied and remove their load_lb
            bad_affinity_reviewers = np.where(
                np.all(
                    (self.affinity_matrix * (self.constraint_matrix == 0).T)
                    == 0,
                    axis=1,
                )
            )[0]
            logging.debug(
                "Setting minimum load for {} reviewers to 0 "
                "because they do not have known affinity with any paper".format(
                    len(bad_affinity_reviewers)
                )
            )
            for rev_id in bad_affinity_reviewers:
                self.minimums[rev_id] = 0

        self.id = uuid.uuid4()
        self.makespan = 0.0  # the minimum allowable paper score.
        self.solution = (
            solution
            if solution
            else np.zeros((self.num_reviewers, self.num_papers))
        )
        self.starter_solution = self.solution.copy()
        self.valid = True if solution else False

        if self.affinity_matrix.shape != self.solution.shape:
            raise SolverException(
                "Affinity Matrix shape does not match the required shape. Affinity Matrix shape {}, expected shape {}".format(
                    self.affinity_matrix.shape, self.solution.shape
                )
            )

        self.max_affinities = np.max(self.affinity_matrix)
        self.big_c = 10000
        self.bigger_c = self.big_c**2

        self.min_cost_flow = pywrapgraph.SimpleMinCostFlow()
        self.start_inds = []
        self.end_inds = []
        self.caps = []
        self.costs = []
        self.source = self.num_reviewers + self.num_papers
        self.sink = self.num_reviewers + self.num_papers + 1
        self.solved = False
        self.logger.debug("End Init FairFlow")

    def _validate_input_range(self):
        """Validate if demand is in the range of min supply and max supply"""
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
                "Total demand ({}) is out of range when min review supply is ({}) and max review supply is ({})".format(
                    demand, min_supply, max_supply
                )
            )

        self.logger.debug("Finished checking graph inputs")

    def objective_val(self):
        """Get the objective value of the RAP."""
        return np.sum(self.sol_as_mat() * self.orig_affinities)

    def _refresh_internal_vars(self):
        """Set start, end, caps, costs to be empty."""
        self.min_cost_flow = pywrapgraph.SimpleMinCostFlow()
        self.start_inds = []
        self.end_inds = []
        self.caps = []
        self.costs = []

    def _grp_paps_by_ms(self):
        """Group papers by makespan.

        Divide papers into 3 groups based on their paper scores. A paper score
        is the sum affinities among all reviewers assigned to review that paper.
        The first group will contain papers with paper scores greater than or
        equal to the makespan.  The second group will contain papers with paper
        scores less than the makespan but greater than makespan - maxaffinity.
        The third group will contain papers with papers scores less than
        makespan - maxaffinity.

        Args:
            None

        Returns:
            A 3-tuple of paper ids.
        """
        paper_scores = np.sum(self.solution * self.affinity_matrix, axis=0)
        g1 = np.where(paper_scores >= self.makespan)[0]
        g2 = np.intersect1d(
            np.where(self.makespan > paper_scores),
            np.where(paper_scores >= self.makespan - self.max_affinities),
        )
        g3 = np.where(self.makespan - self.max_affinities > paper_scores)[0]

        return g1, g2, g3

    def _worst_reviewer(self, papers):
        """Get the worst reviewer from each paper in the input.

        Args:
            papers - numpy array of paper indices.

        Returns:
            A tuple of rows and columns of the
        """
        mask = (self.solution - 1.0) * -self.big_c
        tmp = (mask + self.affinity_matrix).astype("float")
        worst_revs = np.argmin(tmp, axis=0)
        return worst_revs[papers], papers

    def _construct_and_solve_validifier_network(self):
        """Construct a network to make an invalid solution valid.

        To do this we need to ensure that:
            1) each load upper bound is satisfied
            2) each paper coverage constraint is satisfied.

        Returns:
            None -- modifies the internal min_cost_flow network.
        """
        # First solve flow with lower bounds as caps.
        # Construct edges between the source and each reviewer that must review.
        if self.minimums is not None:
            logging.debug("Solving MCF with min load constraint")
            rev_caps = np.maximum(
                self.minimums - np.sum(self.solution, axis=1), 0
            )
            flow = np.sum(rev_caps)
            pap_caps = np.maximum(
                self.demands - np.sum(self.solution, axis=0), 0
            )
            if flow > 0:
                self._construct_graph_and_solve(
                    self.num_reviewers,
                    self.num_papers,
                    rev_caps,
                    pap_caps,
                    self.affinity_matrix,
                    flow,
                )

        # Now compute the residual flow that must be routed so that each paper
        # is sufficiently reviewed. Also compute residual maximums and demands.
        logging.debug("solving MCF with max load constraint")
        rev_caps = self.maximums - np.sum(self.solution, axis=1)
        pap_caps = np.maximum(self.demands - np.sum(self.solution, axis=0), 0)
        flow = np.sum(pap_caps)
        self._construct_graph_and_solve(
            self.num_reviewers,
            self.num_papers,
            rev_caps,
            pap_caps,
            self.affinity_matrix,
            flow,
        )

        # Finally, check validity and return.
        if not (np.all(np.sum(self.solution, axis=0) == self.demands)):
            raise SolverException(
                "Invalid solution. Constructed graph does not match the required review demands for all the papers."
            )
        if not (np.all(np.sum(self.solution, axis=1) <= self.maximums)):
            raise SolverException(
                "Invalid solution. Constructed graph does not satisfy the maximum paper limit for all the reviewers."
            )
        if self.minimums is not None:
            if not (np.all(np.sum(self.solution, axis=1) >= self.minimums)):
                raise SolverException(
                    "Invalid solution. Constructed graph does not satisfy the minimum paper limit for all the reviewers."
                )

        self.valid = True
        return self.solution

    def _construct_ms_improvement_network(self, g1, g2, g3):
        """Construct the network that reassigns reviewers to improve makespan.

        We allow for each paper in G1 to have 1 reviewer removed. This
        guarantees that papers in G1 can only fall to G2. Then, we may assign
        each unassigned reviewer to a paper in G2 or G3. Papers in G2 **may**
        have their reviewers unassigned **only if** their score, s, satisfies
        s - r(g2)_max + r(g1)_min > T - max, so that they remain in G2. Then,
        allow all reviewers who were unassigned to be assigned to the available
        papers in G3.

        Args:
            g1 - numpy array of paper ids in group 1 (best).
            g2 - numpy array of paper ids in group 2.
            g3 - numpy array of paper ids in group 3 (worst).

        Returns:
            None -- modifies the internal min_cost_flow network.
        """
        # Must convert to python ints first.
        g1 = [int(x) for x in g1]
        g2 = [int(x) for x in g2]
        g3 = [int(x) for x in g3]

        pap_scores = np.sum(self.solution * self.affinity_matrix, axis=0)

        # First construct edges between the source and each pap in g1.
        self._refresh_internal_vars()
        for i in range(np.size(g1)):
            self.start_inds.append(self.source)
            self.end_inds.append(self.num_reviewers + g1[i])
            self.caps.append(1)
            self.costs.append(0)

        # Next construct the sink node and edges to each paper in g3.
        papers_needing_no_assignments = 0
        for i in range(np.size(g3)):
            if not self.demands[g3[i]]:
                continue
            self.start_inds.append(self.num_reviewers + g3[i])
            self.end_inds.append(self.sink)
            edge_capacity = 1
            self.caps.append(edge_capacity)
            self.costs.append(0)
            papers_needing_no_assignments += 1 - edge_capacity

        # For each paper in g2, create a dummy node the restricts the flow to
        # that paper to 1.
        for pap2 in g2:
            self.start_inds.append(
                self.num_reviewers + self.num_papers + 2 + pap2
            )
            self.end_inds.append(self.num_reviewers + pap2)
            self.caps.append(1)
            self.costs.append(0)

        # For each assignment in the g1 group, reverse the flow.
        revs, paps1 = np.nonzero(self.solution[:, g1])
        assignment_to_give = set()
        added = set()
        pg2_to_minaff = defaultdict(lambda: np.inf)  # min incoming affinity.
        for i in range(np.size(revs)):
            rev = int(revs[i])
            pap = g1[paps1[i]]
            assert self.solution[rev, pap] == 1.0
            self.start_inds.append(self.num_reviewers + pap)
            self.end_inds.append(rev)
            self.caps.append(1)
            self.costs.append(0)
            assignment_to_give.add(rev)

            # and now connect this reviewer to each dummy paper associate with
            # a paper in g2 if that rev not already been assigned to that paper.
            if rev not in added:
                for pap2 in g2:
                    if (
                        self.solution[rev, pap2] == 0.0
                        and self.constraint_matrix[pap2, rev] == 0.0
                    ):
                        rp_aff = self.affinity_matrix[rev, pap2]
                        if self.allow_zero_score_assignments or rp_aff != 0.0:
                            self.start_inds.append(rev)
                            self.end_inds.append(
                                self.num_reviewers + self.num_papers + 2 + pap2
                            )
                            pg2_to_minaff[pap2] = min(
                                pg2_to_minaff[pap2], rp_aff
                            )

                            self.caps.append(1)
                            self.costs.append(0)
                added.add(rev)
        # For each paper in g2, reverse the flow to assigned revs only if the
        # reversal, plus the min edge coming in from G1 wouldn't violate ms.
        revs, paps2 = np.nonzero(self.solution[:, g2])
        for i in range(np.size(revs)):
            rev = int(revs[i])
            pap = g2[paps2[i]]
            pap_score = pap_scores[pap]
            assert self.solution[rev, pap] == 1.0
            min_in = pg2_to_minaff[pap]
            rp_aff = self.affinity_matrix[rev, pap]
            # lower bound on new paper score.
            lower_bound = pap_score + min_in - rp_aff
            ms_satisfied = (self.makespan - self.max_affinities) <= lower_bound
            if min_in < np.inf and ms_satisfied:
                self.start_inds.append(self.num_reviewers + pap)
                self.end_inds.append(rev)
                self.caps.append(1)
                self.costs.append(0)
                assignment_to_give.add(rev)

        # For each reviewer, connect them to a paper in g3 if not assigned.
        for rev in assignment_to_give:
            for pap3 in g3:
                if (
                    self.solution[rev, pap3] == 0.0
                    and self.constraint_matrix[pap3, rev] == 0.0
                ):
                    rp_aff = self.affinity_matrix[rev, pap3]
                    if self.allow_zero_score_assignments or rp_aff != 0.0:
                        self.start_inds.append(rev)
                        self.end_inds.append(self.num_reviewers + pap3)
                        self.caps.append(1)
                        lb = self.makespan - self.max_affinities
                        pap_score = pap_scores[pap3]
                        # give a bigger reward if assignment would improve group.
                        if rp_aff + pap_score >= lb:
                            self.costs.append(
                                int(-1.0 - self.bigger_c * rp_aff)
                            )
                        else:
                            self.costs.append(int(-1.0 - self.big_c * rp_aff))

        flow = int(
            min(np.size(g3) - papers_needing_no_assignments, np.size(g1))
        )
        self.supplies = np.zeros(self.num_reviewers + self.num_papers + 2)
        self.supplies[self.source] = flow
        self.supplies[self.sink] = -flow

        for i in range(len(self.start_inds)):
            self.min_cost_flow.AddArcWithCapacityAndUnitCost(
                self.start_inds[i],
                self.end_inds[i],
                self.caps[i],
                self.costs[i],
            )
        for i in range(len(self.supplies)):
            self.min_cost_flow.SetNodeSupply(i, int(self.supplies[i]))

    def solve_ms_improvement(self):
        """Reassign reviewers to improve the makespan.

        After solving min-cost-flow in the improvement network, record the
        corresponding solution. In particular, if we have flow leaving a paper
        and entering a reviewer, unassign the reviewer from that paper. If we
        have flow leaving a reviewer and entering a paper, assign the reviewer
        to that paper.
        """
        solver_status = self.min_cost_flow.Solve()
        if solver_status == self.min_cost_flow.OPTIMAL:
            num_un = 0
            for arc in range(self.min_cost_flow.NumArcs()):
                # Can ignore arcs leading out of source or into sink.
                if (
                    self.min_cost_flow.Tail(arc) != self.source
                    and self.min_cost_flow.Head(arc) != self.sink
                ):
                    if self.min_cost_flow.Flow(arc) > 0:
                        # flow goes from tail to head
                        head = self.min_cost_flow.Head(arc)
                        tail = self.min_cost_flow.Tail(arc)
                        if head >= self.num_reviewers + self.num_papers + 2:
                            # this is an edge that restricts flow to a paper
                            pap = head - (
                                self.num_reviewers + self.num_papers + 2
                            )
                            rev = tail
                            assert self.solution[rev, pap] == 0.0
                            self.solution[rev, pap] = 1.0
                        elif tail >= self.num_reviewers + self.num_papers + 2:
                            continue
                        elif head >= self.num_reviewers:
                            pap = head - self.num_reviewers
                            rev = tail
                            assert self.solution[rev, pap] == 0.0
                            self.solution[rev, pap] = 1.0
                            num_un += 1
                        else:
                            rev = head
                            pap = tail - self.num_reviewers
                            assert self.solution[rev, pap] == 1.0
                            self.solution[rev, pap] = 0.0
            self.valid = False
        else:
            raise SolverException(
                "There was an issue with the min cost flow input. "
                "[solve_ms_improvement] SOLVER_STATUS: {}".format(
                    solver_status
                )
            )

    def solve_validifier(self):
        """Reassign reviewers to make the matching valid."""
        solver_status = self.min_cost_flow.Solve()
        if solver_status == self.min_cost_flow.OPTIMAL:
            for arc in range(self.min_cost_flow.NumArcs()):
                # Can ignore arcs leading out of source or into sink.
                if (
                    self.min_cost_flow.Tail(arc) != self.source
                    and self.min_cost_flow.Head(arc) != self.sink
                ):
                    if self.min_cost_flow.Flow(arc) > 0:
                        rev = self.min_cost_flow.Tail(arc)
                        pap = self.min_cost_flow.Head(arc) - self.num_reviewers
                        assert self.solution[rev, pap] == 0.0
                        self.solution[rev, pap] = 1.0

            if not (np.all(np.sum(self.solution, axis=0) == self.demands)):
                raise SolverException(
                    "Invalid solution. Constructed graph does not match the required review demands for all the papers."
                )
            if not (np.all(np.sum(self.solution, axis=1) <= self.maximums)):
                raise SolverException(
                    "Invalid solution. Constructed graph does not satisfy the maximum paper limit for all the reviewers."
                )

            self.valid = True
        else:
            raise SolverException(
                "There was an issue with the min cost flow input. "
                "[solve_validifier] SOLVER_STATUS: {}".format(solver_status)
            )

    def sol_as_mat(self):
        if self.valid:
            return self.solution
        else:
            raise SolverException(
                "You must have solved the model optimally or suboptimally "
                "before calling this function."
            )

    def try_improve_ms(self):
        """Try to improve the minimum paper score.

        Construct the refinement network (that routes assignments from the
        group of papers with high paper score to low paper scores) and solve the
        corresponding min cost flow problem. Then, remove the worst reviewer
        from each paper with more than the required number of reviewers.
        Finally, construct the validifier network to route available reviewers
        to papers missing a reviewer.

        Args:
            None

        Returns:
            A tuple of the size of the top group (papers with highest paper
            scores) and the size of the bottom group (papers with the lowest
            paper scores).
        """
        self._refresh_internal_vars()
        if not np.all(np.sum(self.solution, axis=0) == self.demands):
            self._construct_and_solve_validifier_network()

        g1, g2, g3 = self._grp_paps_by_ms()
        old_g1, old_g2, old_g3 = set(g1), set(g2), set(g3)
        if np.size(g1) > 0 and np.size(g3) > 0:
            self._refresh_internal_vars()
            # Unassign the worst reviewer from each paper in g3.
            w_revs, w_paps = self._worst_reviewer(g3)
            self.solution[w_revs, w_paps] = 0.0

            # Try to route reviewers from the top group to the bottom.
            self._construct_ms_improvement_network(g1, g2, g3)
            self.solve_ms_improvement()

            # Construct a valid solution.
            self._construct_and_solve_validifier_network()

            # Checks: the bottom group should never grow in size.
            g1, g2, g3 = self._grp_paps_by_ms()

            if len(g3) > len(old_g3):
                raise SolverException(
                    "The negative paper group should never grow in size"
                )

            return np.size(g1), np.size(g3)
        else:
            return np.size(g1), np.size(g3)

    def _construct_graph_and_solve(self, n_rev, n_pap, _caps, _covs, ws, flow):
        """Solve min-cost-flow.

        Args:
            n_rev - (int) number of reviewers (sources)
            n_pap - (int) number of papers (sinks)
            _caps - (array of ints) capacities for each reviewer
            _covs - (array of ints) demands for each paper
            ws - (matrix) affinities between reviewers and papers.
            flow - (int) total flow from revs to paps (some of demands)

        Returns:
            None -- but sets self.solution to be a binary matrix containing the
            assignment of reviewers to papers.
        """
        source = n_rev + n_pap
        sink = n_rev + n_pap + 1

        mcf = pywrapgraph.SimpleMinCostFlow()

        # edges from source to reviewers.
        for i in range(n_rev):
            if int(_caps[i]) > 0:
                mcf.AddArcWithCapacityAndUnitCost(source, i, int(_caps[i]), 0)

        # edges from reviewers to papers.
        for i in range(n_rev):
            for j in range(n_pap):
                arc_cap = 1
                if self.solution[i, j] == 1:
                    continue

                edge_constraint = self.constraint_matrix[(j, i)]

                # a constraint of 0 means there's no constraint, so apply the cost as normal, so add an arc normally
                # a constraint of 1 means that this user was explicitly assigned to this paper. We do not support positive constraints right now, so, do not add an arc
                # a constraint of anything other that 0 or 1 essentially indicates a conflict, so do not add an arc
                if edge_constraint == 0 and (
                    self.allow_zero_score_assignments or ws[i, j] != 0
                ):
                    # Costs must be integers. Also, we have affinities so make the "costs" negative affinities.
                    mcf.AddArcWithCapacityAndUnitCost(
                        i,
                        n_rev + j,
                        int(arc_cap),
                        int(-1.0 - self.big_c * ws[i, j]),
                    )

        # edges from papers to sink.
        for j in range(n_pap):
            if int(_covs[j]) > 0:
                mcf.AddArcWithCapacityAndUnitCost(
                    n_rev + j, sink, int(_covs[j]), 0
                )

        supplies = np.zeros(n_rev + n_pap + 2)
        supplies[source] = int(flow)
        supplies[sink] = int(-flow)

        # set Node supply for this MCF.
        for i in range(len(supplies)):
            mcf.SetNodeSupply(i, int(supplies[i]))

        # Solve.
        solver_status = mcf.Solve()
        if solver_status == mcf.OPTIMAL:
            for arc in range(mcf.NumArcs()):
                # Can ignore arcs leading out of source or into sink.
                if mcf.Tail(arc) != source and mcf.Head(arc) != sink:
                    if mcf.Flow(arc) > 0:
                        rev = mcf.Tail(arc)
                        pap = mcf.Head(arc) - n_rev
                        assert self.solution[rev, pap] == 0.0
                        self.solution[rev, pap] = 1.0
            self.solved = True
        else:
            raise SolverException(
                "Solver could not find a solution. Adjust your parameters. "
                "[_construct_graph_and_solve] SOLVER_STATUS: {}".format(
                    solver_status
                )
            )

    def find_ms(self):
        """Find the highest possible makespan.

        Perform a binary search on the makespan value. Solve the RAP with each
        makespan value and return the solution corresponding to the makespan
        which achieves the largest minimum paper score.

        Args:
            None

        Return:
            Highest feasible makespan value found.
        """
        mn = 0.0
        mx = np.max(self.affinity_matrix) * np.max(self.demands)
        ms = (mx - mn) / 2.0
        self.makespan = ms
        best = None
        best_worst_pap_score = 0.0

        for i in range(10):
            self.logger.debug("#info FairFlow:ITERATION %s ms %s" % (i, ms))
            try:
                s1, s3 = self.try_improve_ms()
                self.logger.debug("Round 0: s1 {} s3 {}".format(s1, s3))
                can_improve_round_counter = 1
                can_improve = s3 > 0
                prev_s1, prev_s3 = -1, -1
                while can_improve and prev_s3 != s3:
                    prev_s1, prev_s3 = s1, s3
                    start = time.time()
                    s1, s3 = self.try_improve_ms()
                    self.logger.debug(
                        "Round {}: s1 {} s3 {}".format(
                            can_improve_round_counter, s1, s3
                        )
                    )
                    can_improve_round_counter += 1
                    can_improve = s3 > 0
                    self.logger.debug(
                        "#info FairFlow:try_improve takes: %s s"
                        % (time.time() - start)
                    )

                worst_pap_score = np.min(
                    np.sum(self.solution * self.affinity_matrix, axis=0)
                )
                self.logger.debug(
                    "#info FairFlow:best worst paper score %s worst score %s"
                    % (best_worst_pap_score, worst_pap_score)
                )

                success_c1 = s3 == 0
                success_c2 = np.all(
                    self.affinity_matrix[self.solution.astype(np.bool)] != 0
                )
                success = success_c1 & (
                    self.allow_zero_score_assignments | success_c2
                )
                self.logger.debug(
                    "#info FairFlow:success = %s [success_c1: %s, success_c2: %s]"
                    % (success, success_c1, success_c2)
                )
            except SolverException as error_handle:
                self.logger.debug("No Solution={}".format(error_handle))
                worst_pap_score = -np.inf
                success = False
                self.logger.debug("#info FairFlow:success = %s" % success)

            if success and worst_pap_score >= best_worst_pap_score:
                best = ms
                best_worst_pap_score = worst_pap_score
                mn = ms
                ms += (mx - ms) / 2.0
            else:
                mx = ms
                ms -= (ms - mn) / 2.0
            self.makespan = ms
            self.solution = self.starter_solution.copy()
        self.logger.debug("#info FairFlow:Best found %s" % best)
        self.logger.debug(
            "#info FairFlow:Best Worst Paper Score found %s"
            % best_worst_pap_score
        )
        if best is None:
            return 0.0
        else:
            return best

    def solve(self):
        """Find a makespan and solve flow.

        Run a binary search to find best makespan and return the corresponding
        solution.

        Args:
            None

        Returns:
            The solution as a matrix.
        """

        self._validate_input_range()
        ms = self.find_ms()
        self.makespan = ms
        s1, s3 = self.try_improve_ms()
        can_improve = s3 > 0
        prev_s1, prev_s3 = -1, -1
        while can_improve and (prev_s1 != s1 or prev_s3 != s3):
            prev_s1, prev_s3 = s1, s3
            s1, s3 = self.try_improve_ms()
            can_improve = s3 > 0

        return self.sol_as_mat().transpose()
