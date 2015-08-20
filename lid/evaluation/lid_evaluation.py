
from text_alignment import *    
from lid import *
import numpy as np
import time
import pickle


#constants
EVALUATION_INDEX = 'evaluation_texts'


def alignment_mean(alignments):
    '''
	alignments is list of dictionaries with field 'score'
    '''
    return np.mean([alignment['score'] for alignment in alignments])

class LIDExperiment():
    def __init__(self, aligner = LocalAligner(), get_score = alignment_mean, 
                split_sections = False, query_results_limit=100,lucene_score_threshold = 0.1):
        '''
		get_score is way to aggregate to document level from multiple alignments
        '''
        self.lid = LID(aligner = LocalAligner(), query_results_limit=query_results_limit, 
                        lucene_score_threshold = lucene_score_threshold)
        self.lucene_score_threshold = lucene_score_threshold
        self.query_results_limit = query_results_limit
        self.alignment_docs = {}
        self.results = {}
        self.get_score = get_score
        self.split_sections = split_sections
        self.time_to_finish = None
        self.lucene_recall = None
        self.to_save = {}


    def evaluate_system(self):
        '''
        evaluate both alignment and lucene aspects of system
        '''
        self.evaluate_alignment()
        self.evaluate_lucene_score()

        self.to_save['lucene_score_threshold'] = self.lucene_score_threshold
        self.to_save['query_results_limit'] = self.query_results_limit
        self.to_save['split_sections'] = self.split_sections
        self.to_save['time_to_finish'] = self.time_to_finish
        self.to_save['results'] = self.results
        self.to_save['lucene_recall'] = self.lucene_recall

    def evaluate_alignment(self):
        start_time = time.time()
        doc_ids = self.lid.elastic_connection.get_all_doc_ids(EVALUATION_INDEX)
        num_bills = len(doc_ids)
        for query_id in doc_ids:

            print('working on query_id {0}....'.format(query_id))
            print('completed {0:.2f}%'.format((float(query_id)+1)/num_bills))
            if int(query_id) > 0:
                print('estimated time left: {0} minutes'.format(
                    ((iteration_end_time - iteration_start_time )*(num_bills - int(query_id)))/60))

            iteration_start_time = time.time()

            print('grabbing bill....')
            query_bill = self.lid.elastic_connection.get_bill_by_id(query_id, index = EVALUATION_INDEX)
            query_text = query_bill['bill_document_last']

            print('finding alignments....')
            if query_bill['state'] == 'model_legislation':
                alignment_docs = self.lid.find_evaluation_alignments(query_text, document_type = "model_legislation",
                                                        query_document_id = query_id,
                                                        split_sections = self.split_sections)
            else:
                alignment_docs = self.lid.find_evaluation_alignments(query_text, document_type = "state_bill", 
                                                        state_id = query_bill['state'], query_document_id = query_id,
                                                        split_sections = self.split_sections)

            self.alignment_docs[query_id] = alignment_docs

            print('storing alignment results....')
            for result in alignment_docs['alignment_results']:

                result_id = result['document_id']
                #we are not interested in case where they are the same
                if query_id == result_id:
                    continue
                #if we already have record and we do not split section, the score is symmetric
                if not self.split_sections and (result_id, query_id) in self.results:
                    continue

                self.results[(query_id, result_id)] = {}
                result_bill = self.lid.elastic_connection.get_bill_by_id(result_id, index = EVALUATION_INDEX)

                self.results[(query_id, result_id)]['match'] = (query_bill['match'] == result_bill['match'])
                self.results[(query_id, result_id)]['lucene_score'] = result['lucene_score']
                self.results[(query_id, result_id)]['score'] = self.get_score(result['alignments'])

            iteration_end_time = time.time()

        print('filling in rest of results....')
        for query_id in doc_ids:
            query_bill = self.lid.elastic_connection.get_bill_by_id(query_id, index = EVALUATION_INDEX)
            for doc_id in doc_ids:
                doc_bill = self.lid.elastic_connection.get_bill_by_id(doc_id, index = EVALUATION_INDEX)

                if doc_id == query_id:
                    continue
                if self.split_sections:
                    if (query_id, doc_id) not in self.results:
                        self._add_zero_entry_to_entries(query_id, doc_id, query_bill, doc_bill)

                    if (doc_id, query_id) not in self.results:
                        self._add_zero_entry_to_entries(query_id, doc_id, doc_bill, query_bill)
                else:
                    if (query_id, doc_id) in self.results or (doc_id, query_id) in self.results:
                        continue
                    else:
                        self._add_zero_entry_to_entries(query_id, doc_id, query_bill, doc_bill)

        self.time_to_finish = time.time() - start_time

        # print('calculate lucene recall score....')
        # self._calculate_lucene_recall()


    def evaluate_lucene_score(self):
        '''
        evaluate recall of lucene score
        '''
        doc_ids = self.lid.elastic_connection.get_all_doc_ids(EVALUATION_INDEX)
        num_bills = len(doc_ids)
        for query_id in doc_ids:

            query_bill = self.lid.elastic_connection.get_bill_by_id(query_id, index = EVALUATION_INDEX)
            query_text = query_bill['bill_document_last']

            print('working on query_id {0}....'.format(query_id))
            print('completed {0:.2f}%'.format((float(query_id)+1)/num_bills))

            if query_bill['state'] == 'model_legislation':
                evaluation_docs = self.lid.find_evaluation_texts(query_text, document_type = "model_legislation",
                                                        query_document_id = query_id,
                                                        split_sections = self.split_sections)
            else:
                evaluation_docs = self.lid.find_evaluation_texts(query_text, document_type = "state_bill", 
                                                        state_id = query_bill['state'], query_document_id = query_id,
                                                        split_sections = self.split_sections)

            print('storing lucene results....')
            for result in evaluation_docs:

                result_id = result['id']
                #we are not interested in case where they are the same
                if query_id == result_id:
                    continue

                result_bill = self.lid.elastic_connection.get_bill_by_id(result_id, index = EVALUATION_INDEX)

                if (query_id, result_id) not in self.results:
                    self.results[(query_id, result_id)] = {}

                self.results[(query_id, result_id)]['match'] = (query_bill['match'] == result_bill['match'])
                print 'lucene_score: ', result['score']
                self.results[(query_id, result_id)]['lucene_score'] = result['score']

        print('filling in rest of results....')
        for query_id in doc_ids:
            query_bill = self.lid.elastic_connection.get_bill_by_id(query_id, index = EVALUATION_INDEX)
            for doc_id in doc_ids:
                doc_bill = self.lid.elastic_connection.get_bill_by_id(doc_id, index = EVALUATION_INDEX)

                if doc_id == query_id:
                    continue
                if (query_id, doc_id) not in self.results:
                    self.results[(query_id, doc_id)] = {}
                    self.results[(query_id, doc_id)]['lucene_score'] = 0
                    self.results[(query_id, doc_id)]['match'] = (query_bill['match'] == result_bill['match'])

        print('calculate lucene recall score....')
        self._calculate_lucene_recall()


    def _calculate_lucene_recall(self):
        lucene_recall = []
        for key,value in self.results.items():
            if value['match'] == 1:
                if value['lucene_score'] < self.lucene_score_threshold:
                    lucene_recall.append(0)
                else:
                    lucene_recall.append(1)

        self.lucene_recall = np.mean(lucene_recall)


    def _add_zero_entry_to_entries(self, query_id, doc_id, query_bill, doc_bill):
        self.results[(query_id, doc_id)] = {}
        self.results[(query_id, doc_id)]['match'] = (query_bill['match'] == doc_bill['match'])
        self.results[(query_id, doc_id)]['lucene_score'] = 0
        self.results[(query_id, doc_id)]['alignment_score'] = 0 


    def plot_roc(self):
        truth = [value['match'] for key, value in self.results.items()]
        score = [value['score'] for key, value in self.results.items()]

        roc = roc_curve(truth, score)
        fpr = roc[0]
        tpr = roc[1]
        roc_auc = auc(fpr, tpr)

        plt.figure()
        plt.plot(fpr, tpr, label='ROC curve (area = %0.2f)' % roc_auc)
        plt.plot([0, 1], [0, 1], 'k--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver operating characteristic example')
        plt.legend(loc="lower right")
        plt.show()

    def save(self, name):

        with open('{0}.p'.format(name), 'wb') as fp:
            pickle.dump(self.to_save, fp)

########################################################################################################################

class GridSearch():

    def __init__(self, aligner = LocalAligner, match_scores = [2,3,4], mismatch_scores = [-1,-2,-3], 
                gap_scores = [-1,-2,-3], gap_starts = [-2,-3,-4], gap_extends = [-0.5,-1,-1.5], 
                query_results_limit=100, lucene_score_threshold = 0.1, 
                lucene_score_thresholds = np.arange(0.1,1,0.05)):
        self.aligner = aligner
        self.grid = {}
        self.grid_df = None
        self.match_scores = match_scores
        self.mismatch_scores = mismatch_scores
        self.gap_scores = gap_scores
        self.gap_starts = gap_starts
        self.gap_extends = gap_extends
        self.lucene_score_performance = {}
        self.lucene_score_threshold = lucene_score_threshold
        self.lucene_score_thresholds = lucene_score_thresholds


    def search_lucene_scores(self):
        for lucene_score in self.lucene_score_thresholds:
            print('working on lucene score {0}....'.format(lucene_score))
            l = LIDExperiment(lucene_score_threshold = lucene_score)
            l.evaluate_lucene_score()
            self.lucene_score_performance[lucene_score] = l.lucene_recall

    def evaluate_system(self):
        #only works for doc experiemnt currently
        #determine parameters to do grid search on for given algorithm
        if self.aligner == LocalAligner:    
            for match_score in self.match_scores:
                for mismatch_score in self.mismatch_scores:
                    for gap_score in self.gap_scores:

                        print 'running LocalAligner model: match_score {0} mismatch_score {1} gap_score {2}'.format(match_score, mismatch_score, gap_score)

                        l = LIDExperiment(aligner = self.aligner(match_score, mismatch_score, gap_score), 
                                        lucene_score_threshold = self.lucene_score_threshold)

                        l.evaluate_system()

                        self.grid[(match_score, mismatch_score, gap_score)] = l.to_save

        elif self.aligner == AffineLocalAligner:
            for match_score in self.match_scores:
                for mismatch_score in self.mismatch_scores:
                    for gap_start in self.gap_starts:
                        for gap_extend in self.gap_extends:

                            print 'running AffineLocalAligner model: match_score {0} mismatch_score {1} \
                                    gap_start {2} gap_extend'.format(match_score, mismatch_score,
                                                                     gap_start, gap_extend)

                            l = LIDExperiment(aligner = self.aligner(match_score, mismatch_score, gap_start, gap_extend), 
                                            lucene_score_threshold = self.lucene_score_threshold)

                            l.evaluate_system()

                            self.grid[(match_score, mismatch_score, gap_start, gap_extend)] = l.to_save                      

            return self.grid


    def plot_roc(self):
        experiments = [(str(key), value) for key,value in self.grid.items()]
        roc_experiments(experiments)


    def save(self, name):
        with open('{0}.p'.format(name), 'wb') as fp:
            pickle.dump(self, fp)



############################################################
##analysis functions
def roc_experiments(experiments):
    '''
    args:
        experiments : list of tuples where first entry is name of experiment and second entry is experiment object
    returns:
        roc plot of all the experiments
    '''
    fpr = dict()
    tpr = dict()
    roc_auc = dict()
    for i in range(len(experiments)):
        truth = [value['match'] for key, value in experiments[i][1]['results'].items()]   
        score = [value['score'] for key, value in experiments[i][1]['results'].items()]

        roc = roc_curve(truth, score)
        fpr[i] = roc[0]
        tpr[i] = roc[1]
        roc_auc[i] = auc(fpr[i], tpr[i])

    # best_experiments = range(len(experiments))
    #find 5 models with largest auc
    t = [(key,value)  for key,value in  roc_auc.items()]
    best = nlargest(5, t, key=lambda x: x[1])
    best_experiments = [b[0] for b in best]

    # Plot ROC curve
    plt.figure()
    for i in best_experiments:
        plt.plot(fpr[i], tpr[i], label='ROC curve of algorithm {0} (area = {1:0.2f})'
                                       ''.format(experiments[i][0], roc_auc[i]))

    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Comparison of ROC curves of multiple experiments')
    plt.legend(loc="lower right")
    plt.show()


#####
#other functions
def load_pickle(name):
    with open('{0}.p'.format(name),'rb') as fp:
        f =pickle.load(fp)

    return f

if __name__ == "__main__":

    l = LIDExperiment(query_results_limit=1000,lucene_score_threshold = 0.01)
    l.evaluate_lucene_score()
    l.save('local_alignment_experiment_01_1000')

    # l1 = LIDExperiment(query_results_limit=1000,lucene_score_threshold = 0)
    # l1.evaluate_lucene_score()
    # l1.save('local_alignment_experiment_0_1000')

    # g = GridSearch()
    # g.search_lucene_scores()
    # g.evaluate_system()
    # g.save('lucene_grid_experiment')


