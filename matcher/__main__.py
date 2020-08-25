'''
CLI interface for the matcher
'''

import argparse
import csv
import json
from .core import Matcher
from .solvers import MinMaxSolver, FairFlow
import logging
from collections import defaultdict
import time

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

log_format = '%(asctime)s %(levelname)s: [in %(pathname)s:%(lineno)d] %(message)s'
logging.basicConfig(filename="default.log", format=log_format)

consoleHandler = logging.StreamHandler()
logger.addHandler(consoleHandler)

t0 = time.time()
logger.info('Starting time={}'.format(t0))

parser = argparse.ArgumentParser()
parser.add_argument(
    '--scores',
    nargs='+',
    help='''
        One or more score files,
        with each row containing comma-separated paperID, userID, and score (in that order).
        e.g. "paper1,reviewer1,0.5"
        '''
)

parser.add_argument(
    '--constraints',
    help='''
        One or more constraint files,
        with each row containing comma-separated paperID, userID, and constraint (in that order).
        Constraint values must be -1 (conflict), 1 (forced assignment), or 0 (no effect).
        e.g. "paper1,reviewer1,-1"
        '''
)

parser.add_argument(
    '--max_papers',
    help='''
        max paper files,
        with each row containing comma-separated userID, and max_papers that can be assigned to this user (in that order).
        e.g. "reviewer1,2''')


parser.add_argument('--weights', nargs='+', type=float)
parser.add_argument('--min_papers_default', default=0, type=int)
parser.add_argument('--max_papers_default', type=int)
parser.add_argument('--num_reviewers', default=3, type=int)
parser.add_argument('--num_alternates', default=3, type=int)
parser.add_argument('--user_group', type=str)

parser.add_argument(
    '--user_group_file',
    help='''Pass a csv file with each line in the form: "Group1, user_email"'''
)

# TODO: dynamically populate solvers list
# TODO: can argparse throw an error if the solver isn't in the list?
parser.add_argument(
    '--solver',
    help='Choose from: {}'.format(['MinMax', 'FairFlow']),
    default='MinMax'
)

args = parser.parse_args()

# Main Logic
logger.info('Setting solver class')
solver_class = None
if args.solver == 'MinMax':
    solver_class = 'MinMax'
if args.solver == 'FairFlow':
    solver_class = 'FairFlow'

if not solver_class:
    raise ValueError('Invalid solver class {}'.format(args.solver))
logger.info('Using solver={}'.format(solver_class))

reviewer_set = set()
paper_set = set()
logger.info('Using weights={}'.format(args.weights))
weight_by_type = {
    score_file: args.weights[idx] for idx, score_file in enumerate(args.scores)}

scores_by_type = {score_file: {'edges': []} for score_file in args.scores}

for score_file in args.scores:
    logger.info('processing file={}'.format(score_file))
    file_reviewers = []
    file_papers = []

    with open(score_file) as file_handle:

        for row in csv.reader(file_handle):
            paper_id = row[0].strip()
            profile_id = row[1].strip()
            score = row[2].strip()

            file_reviewers.append(profile_id)
            file_papers.append(paper_id)
            scores_by_type[score_file]['edges'].append((paper_id, profile_id, score))

    reviewer_set.update(file_reviewers)
    paper_set.update(file_papers)

constraints = []
if args.constraints:
    with open(args.constraints) as file_handle:
        for row in csv.reader(file_handle):
            paper_id = row[0]
            profile_id = row[1]
            constraint = row[2]

            reviewer_set.update([profile_id])
            paper_set.update([paper_id])

            constraints.append((paper_id, profile_id, constraint))

reviewers = sorted(list(reviewer_set))
papers = sorted(list(paper_set))

user_group_map = defaultdict(list)
if args.user_group_file:
    with open(args.user_group_file) as file_handle:
        for row in csv.reader(file_handle):
            group_id = row[0]
            reviewer_email = row[1]
            user_group_map[group_id].append(reviewer_email)

reviewers_copy = [reviewer for reviewer in reviewers]
if args.user_group:
    selected_reviewers = user_group_map.get(args.user_group)
    for reviewer in reviewers:
        if reviewer not in selected_reviewers:
            reviewers_copy.remove(reviewer)
    reviewers = reviewers_copy

minimums = [args.min_papers_default] * len(reviewers)
maximums = [args.max_papers_default] * len(reviewers)

if args.max_papers:
    missing_reviewers = []
    with open(args.max_papers) as file_handle:
        for idx, row in enumerate(csv.reader(file_handle)):
            profile_id = row[0]
            max_assignment = int(row[1])

            if profile_id in reviewers:
                reviewer_idx = reviewers.index(profile_id)

                maximums[reviewer_idx] = max_assignment
            else:
                missing_reviewers.append(profile_id)
    if missing_reviewers:
        logger.info('Reviewers missing in all score files: ' + ', '.join(profile_id))

demands = [args.num_reviewers] * len(papers)
num_alternates = args.num_alternates

logger.info('Count of reviewers={} '.format(len(reviewers)))
logger.info('Count of papers={}'.format(len(papers)))

match_data = {
    'reviewers': reviewers,
    'papers': papers,
    'constraints': constraints,
    'scores_by_type': scores_by_type,
    'weight_by_type': weight_by_type,
    'minimums': minimums,
    'maximums': maximums,
    'demands': demands,
    'num_alternates': num_alternates,
    'assignment_output': 'assignments.json',
    'alternates_output': 'alternates.json',
    'logger': logger
}

matcher = Matcher(
    datasource=match_data,
    solver_class=solver_class,
    logger=logger
)

matcher.run()
t1 = time.time()
logger.info('Overall execution time: {0} seconds'.format(t1-t0))