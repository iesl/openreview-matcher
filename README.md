[![CircleCI](https://circleci.com/gh/openreview/openreview-matcher.svg?style=svg&circle-token=d20a11c2cb9e46d2a244638d1646ebdf3aa56b39)](https://circleci.com/gh/openreview/openreview-matcher)

# OpenReview Matcher
A tool for computing optimal paper-reviewer matches for peer review, subject to constraints and affinity scores. Comes with a simple web server designed for integration with the OpenReview server application.

Brief explanatation how the matching system works:

https://docs.google.com/presentation/d/1AljO7he87Hn9wnffDYvuk-BT-WPJvv-7-3Ems8O-VG4/edit?usp=sharing

## Installation
Clone the [GitHub repository](https://github.com/openreview/openreview-matcher.git) and install with `pip`:

```
git clone https://github.com/openreview/openreview-matcher.git
pip install ./openreview-matcher
```

## Example Usage

The matcher can be run from the command line. For example:
```
python -m matcher \
	--scores affinity_scores.txt \
	--weights 1 \
	--min_papers_default 1 \
	--max_papers_default 10 \
	--num_reviewers 3 \
	--num_alternates 3
```

Run the module with the `--help` flag to learn about the arguments:
```
python -m matcher --help
```

## Solvers

### MinMax Solver

Basic implementation using the Minimum Cost function implemented in the Google [ortools](https://developers.google.com/optimization/flow/mincostflow) library. MinMax solver tries to optimize the scores respecting the restrictions of min and max quotas for each paper and reviewer.

### FairFlow Solver

Fairflow solver tries to more fairly assign reviewers to papers in a way that each paper has at least some minimum affinity with the reviewers to which it is assigned.

For more information, see [this paper](https://arxiv.org/abs/1905.11924v1)

### Randomized Solver

The randomized solver (`--solver Randomized` on the command line) implements a randomized assignment algorithm. It takes as additional input limits on the marginal probability of each reviewer-paper pair being matched. The solver then finds a randomized assignment that maximizes expected total affinity, subject to the given probability limits. This randomized assignment is found with an LP, implemented in `matcher/solvers/randomized_solver.py`.

The solver returns a deterministic assignment which was sampled from this randomized assignment. The sampling algorithm is implemented in `matcher/solvers/bvn_extension`.

For more information, see [this paper](https://arxiv.org/abs/2006.16437).

### FairSequence Solver

FairSequence (`--solver FairSequence` on the command line) attempts to create an allocation of reviewers that is fair according to the weighted envy-free up to 1 item (WEF1) criterion. This criterion implies that when one paper has a higher average affinity for another papers' reviewers, it is only due to a single reviewer rather than a larger overall imbalance in affinity scores. Reviewers are assigned to papers one-by-one in priority order, with priority given to the papers with the lowest ratio of allocation size to demand. Ties in priority are resolved to favor reviewer-paper assignments with higher affinity.

For more information about the WEF1 fairness criterion, see [this paper](https://dl.acm.org/doi/abs/10.1145/3457166), and for more information about the adaptation to reviewer assignment, see [this paper](https://arxiv.org/abs/2108.02126).

## Running the Server
The server is implemented in Flask and uses Celery to manage the matching tasks asynchronously and can be started from the command line:
```
python -m matcher.service --host localhost --port 5000
```

By default, the app will run on `http://localhost:5000`. The endpoint `/match/test` should show a simple page indicating that Flask is running.

The celery worker can be installed using:
```
 celery --app matcher.service.server.celery_app worker
```

To start multiple workers, run the same command with the name option for each worker as follows:

```
celery --app matcher.service.server.celery_app worker -n worker_name
```
For more options you may check the celery-worker documentation [here](https://docs.celeryproject.org/en/stable/reference/cli.html#celery-worker).

There's also an option to monitor the celery workers using `flower`. Make sure to install the full package:
```
pip install ./openreview-matcher[full]
```
and the flower dashboard can be started after that using
```
celery --app matcher.service.server.celery_app flower --persistent=True --state_save_interval=60000
```
For more options you may check the flower documentation [here](https://flower.readthedocs.io/en/latest/config.html).

By default, the flower dashboard will run on `http://localhost:5555`
### Configuration
Configuration files are located in `/matcher/service/config`. When started, the server will search for a `.cfg` file in `/matcher/service/config` that matches the environment variable `FLASK_ENV`, and will default to the values in `default.cfg`.

For example, with file `/matcher/service/config/development.cfg`:
```
# development.cfg
LOG_FILE='development.log'

OPENREVIEW_USERNAME='OpenReview.net'
OPENREVIEW_PASSWORD='1234'
OPENREVIEW_BASEURL='http://localhost:3000'
```

Start the server with `development.cfg`:
```
FLASK_ENV=development python -m matcher.service
```

Note that Flask will set `FLASK_ENV` to "production" by default, so if a file `production.cfg` exists, and the `FLASK_ENV` variable is unset, then the app will overwrite default values with those in `production.cfg`.

## Unit & Integration Tests (with pytest)

The `/tests` directory contains unit tests and integration tests (i.e. tests that communicate with an instance of the OpenReview server application), written with [pytest](https://docs.pytest.org/en/latest).

### Requirements

Running the tests requires MongDB and Redis to support the OpenReview server instance used in the integration tests.

Before running integration tests, ensure that `mongod` and `redis-server` are running, and that no existing OpenReview instances are active.

Also ensure that OpenReview environment variables are unset:

```
unset OPENREVIEW_USERNAME
unset OPENREVIEW_PASSWORD
unset OPENREVIEW_BASEURL
```

Integration tests use the `test_context` [pytest fixture](https://docs.pytest.org/en/latest/fixture.html), which starts a clean, empty OpenReview instance and creates a mock conference.

### Running the Tests

The entire suite of tests can be run with the following commands from the top level project directory:

    export OPENREVIEW_HOME=<path_to_openreview>
    python -m pytest tests

Individual test modules can be run by passing in the module file as the argument:

	export OPENREVIEW_HOME=<path_to_openreview>
	python -m pytest tests/test_integration.py

