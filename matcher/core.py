"""Contains core matcher functions and classes."""
import logging
import threading
import time
import json
from enum import Enum
from .solvers import (
    SolverException,
    MinMaxSolver,
    FairFlow,
    RandomizedSolver,
    FairSequence,
)
from .encoder import Encoder

SOLVER_MAP = {
    "MinMax": MinMaxSolver,
    "FairFlow": FairFlow,
    "Randomized": RandomizedSolver,
    "FairSequence": FairSequence,
}


class MatcherStatus(Enum):
    INITIALIZED = "Initialized"
    RUNNING = "Running"
    ERROR = "Error"
    NO_SOLUTION = "No Solution"
    COMPLETE = "Complete"
    DEPLOYING = "Deploying"
    DEPLOYED = "Deployed"
    DEPLOYMENT_ERROR = "Deployment Error"
    QUEUED = "Queued"
    CANCELLED = "Cancelled"


class MatcherError(Exception):
    """Exception wrapper class for errors related to Matcher."""

    pass


class KeywordDatasource:
    def __init__(
        self,
        reviewers=[],
        papers=[],
        constraints=[],
        scores_by_type=None,
        weight_by_type=None,
        minimums=[],
        maximums=[],
        demands=[],
        num_alternates=0,
        probability_limits=[],
        allow_zero_score_assignments=False,
        assignments_output="assignments.json",
        alternates_output="alternates.json",
        logger=logging.getLogger(__name__),
    ):

        self.reviewers = reviewers
        self.papers = papers
        self.constraints = constraints
        self.scores_by_type = scores_by_type if scores_by_type else {}
        self.weight_by_type = weight_by_type if weight_by_type else {}
        self.minimums = minimums
        self.maximums = maximums
        self.demands = demands
        self.probability_limits = probability_limits
        self.num_alternates = num_alternates
        self.allow_zero_score_assignments = allow_zero_score_assignments
        self.normalization_types = []
        self.assignments_output = assignments_output
        self.alternates_output = alternates_output
        self.logger = logger
        self.match_group = None

    def set_assignments(self, assignments):
        self.logger.info("Writing assignments to file")
        with open(self.assignments_output, "w") as f:
            f.write(json.dumps(assignments, indent=2))

    def set_alternates(self, alternates):
        self.logger.info("Writing alternates to file")
        with open(self.alternates_output, "w") as f:
            f.write(json.dumps(alternates, indent=2))

    def set_status(self, status, message, additional_status_info={}):
        self.logger.info(
            "status={0}, message={1}, additional_status_info={2}".format(
                status.value, message, additional_status_info
            )
        )

    def validate_group(self, group_id):
        pass


class Matcher:
    """Main class that coordinates an Encoder and a Solver."""

    def __init__(
        self,
        datasource,
        solver_class,
        on_set_status=None,
        logger=logging.getLogger(__name__),
    ):

        if isinstance(datasource, dict):
            self.datasource = KeywordDatasource(**datasource)
        else:
            self.datasource = datasource

        self.logger = logger
        self.solution = None
        self.assignments = None
        self.alternates = None
        self.status = "Initialized"

        self.solver_class = self.__set_solver_class(solver_class)

    def __set_solver_class(self, solver_class):
        return SOLVER_MAP.get(solver_class, MinMaxSolver)

    def set_status(self, status, message=None, additional_status_info={}):
        self.status = status.value
        self.datasource.set_status(
            status,
            message=message,
            additional_status_info=additional_status_info,
        )

    def get_status(self):
        return self.status

    def set_assignments(self, assignments):
        self.assignments = assignments
        self.datasource.set_assignments(assignments)

    def set_alternates(self, alternates):
        self.alternates = alternates
        self.datasource.set_alternates(alternates)

    def run(self):
        """
        Compute a match of reviewers to papers and post it to the as assignment notes.
        The config note's status field will be set to reflect completion or errors.
        """
        try:
            self.logger.info("Validating Match Group")
            self.datasource.validate_group(self.datasource.match_group)

            self.set_status(MatcherStatus.RUNNING)

            self.logger.debug("Start encoding")

            encoder = Encoder(
                reviewers=self.datasource.reviewers,
                papers=self.datasource.papers,
                constraints=self.datasource.constraints,
                scores_by_type=self.datasource.scores_by_type,
                weight_by_type=self.datasource.weight_by_type,
                normalization_types=self.datasource.normalization_types,
                probability_limits=self.datasource.probability_limits,
                logger=self.logger,
            )

            self.logger.debug("Preparing solver")

            # solver
            solver = self.solver_class(
                self.datasource.minimums,
                self.datasource.maximums,
                self.datasource.demands,
                encoder,
                allow_zero_score_assignments=self.datasource.allow_zero_score_assignments,
                logger=self.logger,
            )

            solution = None
            start_time = time.time()

            self.logger.debug("Solving solver")
            solution = solver.solve()

            self.logger.debug(
                "Complete solver run took {} seconds".format(
                    time.time() - start_time
                )
            )

            if solver.solved:
                self.solution = solution
                self.set_assignments(encoder.decode_assignments(solution))
                if hasattr(solver, "get_alternates"):
                    self.set_alternates(
                        encoder.decode_selected_alternates(
                            solver.get_alternates(
                                self.datasource.num_alternates
                            )
                        )
                    )
                else:
                    self.set_alternates(
                        encoder.decode_alternates(
                            solution, self.datasource.num_alternates
                        )
                    )
                additional_status_info = {}
                if hasattr(solver, "get_fraction_of_opt"):
                    additional_status_info[
                        "randomized_fraction_of_opt"
                    ] = solver.get_fraction_of_opt()
                self.set_status(
                    MatcherStatus.COMPLETE,
                    message="",
                    additional_status_info=additional_status_info,
                )
            elif self.get_status() != "No Solution":
                self.logger.debug(
                    "No Solution. Solver could not find a solution. Adjust your parameters"
                )
                self.set_status(
                    MatcherStatus.NO_SOLUTION,
                    message="Solver could not find a solution. Adjust your parameters",
                )

        except SolverException as error_handle:
            self.logger.debug("No Solution={}".format(error_handle))
            self.set_status(
                MatcherStatus.NO_SOLUTION, message=str(error_handle)
            )
        except Exception as error_handle:
            self.logger.debug("Error={}".format(error_handle))
            self.set_status(MatcherStatus.ERROR, message=str(error_handle))
