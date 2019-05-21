import pytest
import time
import numpy as np
from matcher.fields import Configuration
from params import Params
from matcher.assignment_graph.AssignmentGraph import AssignmentGraph, GraphBuilder
from helpers.conference_config import ConferenceConfig
from matcher.encoder import Encoder



#Unit tests that exercise the Encoder class's two public methods: encode and decode.
# Each test builds a conference and then directly calls the Encoder classes methods.   Assertions are then made about the
# constraint and cost matrices within the encoder.
class TestEncoderUnit:

    def setup_class (cls):
        cls.counter = 0

    def setup (self):
        pass


    def test_simple_encode (self, test_util):
        '''
        Build a conference affinity and recommendation.  Verify cost matrix is correct
        :param test_util:
        :return:
        '''
        num_papers = 4
        num_reviewers = 3
        params = Params({Params.NUM_PAPERS: 4,
                         Params.NUM_REVIEWERS: 3,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: 1,
                         Params.REVIEWER_MAX_PAPERS: 2,
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity', 'recommendation'],
                                                Params.SCORE_TYPE: Params.FIXED_SCORE,
                                                Params.FIXED_SCORE_VALUE: 0.01
                                                }
                         })

        or_client = test_util.client
        conf = ConferenceConfig(or_client, test_util.next_conference_count() , params)
        config = conf.get_config_note()
        md = conf.get_metadata_notes()

        enc = Encoder(md, config.content, conf.reviewers)
        cost_matrix = enc.cost_matrix
        shape = cost_matrix.shape
        assert shape == (num_reviewers,num_papers)
        for r in conf.reviewers:
            for p in conf.paper_notes:
                rev_ix = enc.index_by_reviewer[r]
                pap_ix = enc.index_by_forum[p.id]
                assert cost_matrix[rev_ix, pap_ix] == -2




    def test_encode_constraints_locks_and_vetos (self, test_util):
        '''
        lock paper 0: reviewer 0, paper 1: reviewer 1
        veto paper 0: reviewer 1, paper 2: reviewer 0
        :param test_util:
        :return:
        '''
        num_papers = 4
        num_reviewers = 3
        params = Params({Params.NUM_PAPERS: 4,
                         Params.NUM_REVIEWERS: 3,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: 1,
                         Params.REVIEWER_MAX_PAPERS: 2,
                         Params.CONSTRAINTS_CONFIG: {Params.CONSTRAINTS_LOCKS: {0: [0], 1:[1]},
                                                     Params.CONSTRAINTS_VETOS: {0: [1], 2: [0]}},
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity', 'recommendation'],
                                                Params.SCORE_TYPE: Params.FIXED_SCORE,
                                                Params.FIXED_SCORE_VALUE: 0.01
                                                }
                         })

        or_client = test_util.client
        conf = ConferenceConfig(or_client, test_util.next_conference_count(), params)
        config = conf.get_config_note()

        md = conf.get_metadata_notes()

        enc = Encoder(md, config.content, conf.reviewers)
        constraint_matrix = enc.constraint_matrix
        shape = constraint_matrix.shape
        rev_indices = [enc.index_by_reviewer[r] for r in conf.reviewers]
        pap_indices = [enc.index_by_forum[p.id] for p in conf.paper_notes]
        assert shape == (num_reviewers,num_papers)
        # locks
        assert constraint_matrix[rev_indices[0],pap_indices[0]] == 1
        assert constraint_matrix[rev_indices[1],pap_indices[1]] == 1
        # vetos
        assert constraint_matrix[rev_indices[1],pap_indices[0]] == -1
        assert constraint_matrix[rev_indices[0],pap_indices[2]] == -1
        # default
        assert constraint_matrix[rev_indices[0],pap_indices[1]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[3]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[3]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[0]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[1]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[3]] == 0

    def test_encode_conflicts (self, test_util):
        '''
        conflicts paper-0/user-0, paper-1/user-2
        :param test_util:
        :return:
        '''
        num_papers = 4
        num_reviewers = 3
        params = Params({Params.NUM_PAPERS: 4,
                         Params.NUM_REVIEWERS: 3,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: 1,
                         Params.REVIEWER_MAX_PAPERS: 2,
                         Params.CONFLICTS_CONFIG: {0: [0], 1:[2]},
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity', 'recommendation'],
                                                Params.SCORE_TYPE: Params.FIXED_SCORE,
                                                Params.FIXED_SCORE_VALUE: 0.01
                                                }
                         })

        or_client = test_util.client
        conf = ConferenceConfig(or_client, test_util.next_conference_count(), params)
        config = conf.get_config_note()

        md = conf.get_metadata_notes()

        enc = Encoder(md, config.content, conf.reviewers)
        constraint_matrix = enc.constraint_matrix
        rev_indices = [enc.index_by_reviewer[r] for r in conf.reviewers]
        pap_indices = [enc.index_by_forum[p.id] for p in conf.paper_notes]
        shape = constraint_matrix.shape
        assert shape == (num_reviewers,num_papers)
        # conflicts paper-0/user-0, paper-1/user-2
        assert constraint_matrix[rev_indices[0],pap_indices[0]] == -1
        assert constraint_matrix[rev_indices[2],pap_indices[1]] == -1
        # default
        assert constraint_matrix[rev_indices[1],pap_indices[0]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[1]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[3]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[3]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[0]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[3]] == 0


    def test_encode_conflicts_and_constraints (self, test_util):
        '''
        conflicts paper-0/user-0, paper-1/user-2
        vetos: paper-3/users 1,2
        locks: paper-0/user-0, paper-2/user-2

        the lock of paper-0/user-0 will take precedence over the conflict between these two.
        :param test_util:
        :return:
        '''
        num_papers = 4
        num_reviewers = 3
        params = Params({Params.NUM_PAPERS: 4,
                         Params.NUM_REVIEWERS: 3,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: 1,
                         Params.REVIEWER_MAX_PAPERS: 2,
                         Params.CONFLICTS_CONFIG: {0: [0], 1:[2]},
                         Params.CONSTRAINTS_CONFIG: {Params.CONSTRAINTS_VETOS: {3:[1,2]},
                                                     Params.CONSTRAINTS_LOCKS: {0: [0], 2:[2]}

                         },
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity', 'recommendation'],
                                                Params.SCORE_TYPE: Params.FIXED_SCORE,
                                                Params.FIXED_SCORE_VALUE: 0.01
                                                }
                         })

        or_client = test_util.client
        conf = ConferenceConfig(or_client, test_util.next_conference_count(), params)
        config = conf.get_config_note()

        md = conf.get_metadata_notes()

        enc = Encoder(md, config.content, conf.reviewers)
        constraint_matrix = enc.constraint_matrix
        shape = constraint_matrix.shape
        rev_indices = [enc.index_by_reviewer[r] for r in conf.reviewers]
        pap_indices = [enc.index_by_forum[p.id] for p in conf.paper_notes]
        assert shape == (num_reviewers,num_papers)
        # conflicts paper-0/user-0, paper-1/user-2
        #         vetos: paper-3/users 1,2
        #         locks: paper-0/user-0, paper-2/user-2
        #
        #         the lock of paper-0/user-0 will dominate the conflict between these two.
        assert constraint_matrix[rev_indices[0],pap_indices[0]] == 1
        assert constraint_matrix[rev_indices[1],pap_indices[3]] == -1
        assert constraint_matrix[rev_indices[2],pap_indices[1]] == -1
        assert constraint_matrix[rev_indices[2],pap_indices[2]] == 1
        assert constraint_matrix[rev_indices[2],pap_indices[3]] == -1

        # default
        assert constraint_matrix[rev_indices[0],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[1]] == 0
        assert constraint_matrix[rev_indices[0],pap_indices[3]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[2]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[0]] == 0
        assert constraint_matrix[rev_indices[1],pap_indices[1]] == 0
        assert constraint_matrix[rev_indices[2],pap_indices[0]] == 0



    @pytest.mark.skip("Takes several minutes to run")
    def test_big_encode (self, test_util):
        '''
        Build a large conference and make sure cost matrix is correct
        :param test_util:
        :return:
        '''
        num_papers = 500
        num_reviewers = 200
        params = Params({Params.NUM_PAPERS: num_papers,
                         Params.NUM_REVIEWERS: num_reviewers,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: 2,
                         Params.REVIEWER_MAX_PAPERS: 6,
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity', 'bid'],
                                                Params.SCORE_TYPE: Params.FIXED_SCORE,
                                                Params.FIXED_SCORE_VALUE: 0.01
                                                }
                         })

        or_client = test_util.client
        now = time.time()
        conf = ConferenceConfig(or_client, test_util.next_conference_count(), params)
        print("Time to build test conference: ", time.time() - now)
        config = conf.get_config_note()
        now = time.time()
        md = conf.get_metadata_notes()
        print("Time to build metadata edges: ", time.time() - now)
        now = time.time()
        enc = Encoder(md, config.content, conf.reviewers)
        print("Time to encode: ", time.time() - now)
        cost_matrix = enc.cost_matrix
        shape = cost_matrix.shape
        num_scores = len(params.scores_config[Params.SCORE_NAMES_LIST])
        assert shape == (num_reviewers,num_papers)
        for r in conf.reviewers:
            for p in conf.paper_notes:
                rix = enc.index_by_reviewer[r]
                pix = enc.index_by_forum[p.id]
                assert(cost_matrix[rix,pix] == -1*num_scores)


    def test_decode (self, test_util):
        '''
        Test that the decoder produces the expected assignment.   It's necessary to configure
        the inputs to get a predictable solution.   We send a score matrix that forces
        it to choose the expected solution reviewer-0->paper-0, 1->1, 2->2, 3->2
        '''

        # There is a dependency where testing decode means that the Encoder must have first been instantiated.  Encoder's constructor calls encode.
        # decode makes reference to dictionaries built during encode
        score_matrix = np.array([
            [10, 0, 0],
            [0, 10, 0],
            [0, 0, 10],
            [0, 0, 10]
        ])
        num_papers = 3
        num_reviewers = 4
        num_reviews_needed_per_paper = 2
        reviewer_max_papers = 2
        params = Params({Params.NUM_PAPERS: num_papers,
                         Params.NUM_REVIEWERS: num_reviewers,
                         Params.NUM_REVIEWS_NEEDED_PER_PAPER: num_reviews_needed_per_paper,
                         Params.REVIEWER_MAX_PAPERS: reviewer_max_papers,
                         Params.SCORES_CONFIG: {Params.SCORE_NAMES_LIST: ['affinity'],
                                                Params.SCORE_TYPE: Params.MATRIX_SCORE,
                                                Params.SCORE_MATRIX: score_matrix
                                                }
                         })

        or_client = test_util.client
        conf = ConferenceConfig(or_client, test_util.next_conference_count(), params)
        papers = conf.get_paper_notes()
        reviewers = conf.reviewers
        config = conf.get_config_note()
        md = conf.get_metadata_notes()

        enc = Encoder(md, config.content, conf.reviewers)
        cost_matrix = enc.cost_matrix
        constraint_matrix = np.zeros(np.shape(cost_matrix))
        graph_builder = GraphBuilder.get_builder('SimpleGraphBuilder')
        # set demands so that paper-0: 1, paper-1: 1, paper-2: 2
        demands = [0,0,0]
        ix = enc.index_by_forum[papers[0].id]
        demands[ix] = 1
        ix = enc.index_by_forum[papers[1].id]
        demands[ix] = 1
        ix = enc.index_by_forum[papers[2].id]
        demands[ix] = 2

        solver = AssignmentGraph([1] * num_reviewers, [reviewer_max_papers] * num_reviewers, demands, cost_matrix, constraint_matrix, graph_builder)
        solution = solver.solve()

        assignments_by_forum = enc.decode(solution)[0]
        assert assignments_by_forum[papers[0].id][0]['userId'] == reviewers[0]
        assert assignments_by_forum[papers[1].id][0]['userId'] == reviewers[1]
        assert assignments_by_forum[papers[2].id][0]['userId'] in [reviewers[2], reviewers[3]]
        assert assignments_by_forum[papers[2].id][1]['userId'] in [reviewers[2], reviewers[3]]

