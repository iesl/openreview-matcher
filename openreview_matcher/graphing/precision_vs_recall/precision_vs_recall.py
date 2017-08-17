""" Graph the precision vs recall for ranked output of a model """

import os
from operator import itemgetter
import pandas as pd 
import matplotlib.pyplot as plt
import matplotlib

matplotlib.style.use('ggplot')

from openreview_matcher.graphing import base_graphing
from openreview_matcher import utils


class Graphing(base_graphing.Graphing):

    def __init__(self, eval_data, params=None):
        self.eval_data = eval_data 

    def graph(self, ranklists, ax, model_name):
        """ 
        Graphs the precision vs recall based on the model ranked 
        output 
        
        Arguments:
            @ranklists: a list of query papers and their ranked reviewers (descending)
            @ax: matplotlib object
            @model_name: name of the model to graph
        """

        precision_values = self.evaluate_precision(ranklists)
        recall_values = self.evaluate_recall(ranklists)

        df_precision = pd.DataFrame({
            'precision': precision_values,
            'recall': recall_values
        })

        ax = df_precision.plot.scatter(x="recall", y="precision", label=model_name, ax=ax)
        ax.set_title("Precision vs Recall", y=1.08)
        ax.set_ylabel("Precision")
        ax.set_xlabel("Recall")

        return ax

    def setup_ranked_list(self, ranklists):
        """
        Setup the single ranked list for a model
        Combines all of the individual query ranks into one single rank
        """
        new_rank_list = []

        for forum, rank_list in ranklists:
            for reviewer_score in rank_list:
                reviewer = reviewer_score.split(";")[0]
                score = float(reviewer_score.split(";")[1])
                # filter for reviewers that gave a bid value
                has_bid = self.eval_data.reviewer_has_bid(reviewer, forum)
                if has_bid:
                    new_rank_list.append((reviewer, score, forum))
        ranked_reviewers = sorted(
            new_rank_list, key=itemgetter(1), reverse=True)
        return ranked_reviewers

    def reviewer_has_bid(self, reviewer, paper):
        """ Returns True if the reviewer bid on that 'paper' """
        paper_bids = self.bids_by_forum[paper]
        has_bid = [True if bid.signatures[0] == reviewer.decode("utf-8") else False for bid in paper_bids][0]
        return has_bid

    def get_bid_for_reviewer_paper(self, reviewer, paper):
        """
        Gets the bid for the reviewer and the paper
        Returns 0 if the bid is not relevant and 1 if the bid is relevant
        """
        positive_labels = ['I want to review','I can review']
        paper_bids = self.bids_by_forum[paper]
        bid_value = [1 if bid.tag in positive_labels else 0 for bid in paper_bids if bid.signatures[0] == reviewer.decode('utf-8')]
        if len(bid_value) > 0:
            return bid_value[0]
        else:
            return 0

    def evaluate_recall(self, rank_list):
        """ Evaluate against a single ranked list computed by the model """

        ranked_reviewers = self.setup_ranked_list(rank_list)

        scores = []

        positive_bids = 0
        for reviewer, score, forum in ranked_reviewers:
            bid = self.eval_data.get_bid_for_reviewer_paper(reviewer, forum)
            if bid == 1:
                positive_bids +=1

        for m in range(1, len(ranked_reviewers) + 1):
            topM = ranked_reviewers[0: m]
            topM = map(lambda reviewer: (reviewer[0], self.eval_data.get_bid_for_reviewer_paper(reviewer[0], reviewer[2])), topM)
            pos_bids_from_topM = [bid for bid in topM if bid[1] == 1]

            if float(positive_bids) > 0:
                scores.append(float(len(pos_bids_from_topM))/float(positive_bids))
            else:
                scores.append(0.0)
        return scores 


    def evaluate_precision(self, rank_list):
        """
        Evaluate against a single ranked list computed by the model  
        """

        ranked_reviewers = self.setup_ranked_list(rank_list)

        scores = []

        positive_bids = 0
        for reviewer, score, forum in ranked_reviewers:
            bid = self.eval_data.get_bid_for_reviewer_paper(reviewer, forum)
            if bid == 1:
                positive_bids +=1

        for m in range(1, len(ranked_reviewers) + 1):
            topM = ranked_reviewers[0: m]
            topM = map(lambda reviewer: (reviewer[0], self.eval_data.get_bid_for_reviewer_paper(reviewer[0], reviewer[2])), topM)
            pos_bids_from_topM = [bid for bid in topM if bid[1] == 1]
            precision = float(len(pos_bids_from_topM)) / float(m)  # precision => relevant bids retrieved / # of retrieved
            scores.append(precision)

        return scores 