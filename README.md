# openreview-matcher

A package for finding sets of matches between papers and reviewers, subject to constraints and affinity scores.

Frames the task of matching papers to reviewers as a [network flow problem](https://developers.google.com/optimization/assignment/assignment_min_cost_flow).

This is implemented as a Flask RESTful service.   Structure of the project:

'/matcher' contains the python code that implements app including:

'/matcher/app.py' the main app that is run when Flask starts.  Initializes the app.

'/matcher/routes.py' functions that  serve as the endpoints of the service e.g
 
'/matcher/match.py' contains the task function compute_match which runs the match solver in a thread

'/matcher/solver.py' Defines the Solver class which wraps the min cost flow_solver

**Configuration of the app**

Two config.cfg files are read in.  The first is in the top level directory.  It can contain
settings that are use for the app.   A second file is read in from instance/ directory which should
contain settings particular to a users environment.  Those settings will override ones that
were set in the first file.  Settings that are necessary:
OPENREVIEW_BASEURL, LOG_FILE


**Testing:**

test_end_to_end.py is a test suite that tests all aspects of the matcher.  

**Instructions for running this test case with pytest**

This requires running a clean (empty mongo db).  This can be done by running
a local OpenReview service using its scripts/clean_start_app.js with the environment var:
NODE_ENV=circleci like:

```
NODE_ENV=circleci node scripts/clean_start_app.js
```

Note Well: The clean_start_app must be restarted each time before running the end_to_end tests.

To run the end-to-end test suite:

1. Go into the virtual environment for running the matcher (e.g. source venv/bin/activate)

```
cd openreview-matcher
```

```
python -m pytest test_end_to_end.py 
```

*Currently (3/11/19) 5 of these tests fail because the matcher is not correctly
honoring the vetos and constraints set up in the test conference.

**Integration tests**

 test_match is a set of integration tests.  They use a flask test_client which invokes
 the Flask server with TESTING=True.   The server switches to using tests.MockORClient if TESTING=True.
 Otherwise, it uses the openreview.Client to communicate with OpenReview.
 
 A known issue during integration testing:  This app logs to both the console and a file.
 During testing Flask sets the console logging level to ERROR
 Many tests intentionally generate errors and exceptions which means
 they will be logged to the console.  Thus the console during error
 testing will NOT JUST SHOW "OK" messages.  There will be exception stack traces
 shown because of the error logger. 
 
 test_solver is a single unit test that runs the solver on a simple matrix.

**To run it:**

From the command line (must run from toplevel project dir because logging paths are relative to working dir)

cd to project dir (e.g. openreview-matcher)
```
source venv/bin/activate
```
```
export FLASK_APP=matcher/app.py
```
```
flask run
```

This will set the app running on localhost:5000

Test that its running in browser:
http://localhost:5000/match/test


From Intellij IDEA:

There are pre-built run/debug configurations:  _matching_app_ should be used to 
run the app during development and debugging.  N.B.  The _matching_app_ configuration sets Flask running
on port 8050.

