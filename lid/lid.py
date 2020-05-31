from __future__ import division


'''main module for the LID (legislative influence detector) system '''

from database import ElasticConnection
from multiprocessing import Pool
from text_alignment import LocalAligner, AffineLocalAligner
from utils.text_cleaning import clean_document
from utils.general_utils import alignment_tokenizer
import argparse
import json
import logging
import os
import re
import time
import traceback
import pandas as pd
from tqdm import tqdm

#configure environment variables
os.environ['LOGFILE_DIRECTORY'] = os.path.abspath('/Users/hoon/Coding/policy_log/')
os.environ['POLICY_DIFFUSION'] = os.path.abspath('/Users/hoon/Coding/policy_diffusion/')

#configure logging options here
logging.basicConfig(filename="{0}/lid.log".format(os.environ['LOGFILE_DIRECTORY']),
                level=logging.DEBUG)
logging.getLogger('elasticsearch').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


'''custom exception object for LID class'''
class LidException(Exception):
    pass



class LID(object):
    '''LID class that contains all of the central functionality for querying and aligning text between state
    bills and model legistlation'''

    
    def __init__(self,aligner = LocalAligner(),elastic_host = "localhost",elastic_port=9200,
            query_results_limit=60,lucene_score_threshold = 0.01):
        '''
        alignment_object: any object that inherets from abstract class Alignment

        elastic_host: ip adress of the elastic search instance (default: localhost)

        elastic_port: port of the elastic search instance (defualt: 9200)

        num_results_limit: the limit on the number of results to return with the elastic search query (default: 100)
        
        '''
        self.aligner = aligner
        self.elastic_connection = ElasticConnection(host = elastic_host,port = elastic_port)
        self.results_limit = query_results_limit
        self.lucene_score_threshold = lucene_score_threshold
    
    def find_alignment(self, query_txt, query_id):
        '''
        query_txt is a section of the bill PPACA.

        ''' 
        query_txt = clean_document(query_txt)
        result_docs = self.elastic_connection.similar_doc_query(query_txt, num_results=self.results_limit, \
            return_fields = ['section_id', 'section_txt'], index='bills', fields='section_txt')

        align_doc = alignment_tokenizer(query_txt)
        
        alignment_docs = {}
        # alignment_docs['query_document'] = query_txt
        # alignment_docs['alignment_results'] = []

        column_names = ['luceneScore', 'SWalign', 'billSecidA', 'textA', 'billAstart', 'billAend', 'billSecidB','textB', 'billBstart', 'billBend']
        df = pd.DataFrame(columns = column_names)

        for result_doc in result_docs:
            if result_doc['score'] < self.lucene_score_threshold:
                break

            result_sequence = clean_document(result_doc['sec_txt'])
            result_sequence = alignment_tokenizer(result_sequence)
            
            alignment_obj = self.aligner.align([align_doc],[result_sequence])[0]

            df = df.append(pd.DataFrame({
                'luceneScore': result_doc['score'],
                'SWalign': alignment_obj['score'],
                'billSecidA': result_doc['sec_id'],
                'textA': ' '.join(alignment_obj['right']),
                'billAstart': alignment_obj['right_start'],
                'billAend': alignment_obj['right_end'],
                'billSecidB': query_id,
                'textB': ' '.join(alignment_obj['left']),
                'billBstart': alignment_obj['left_start'],
                'billBend': alignment_obj['left_end']            
            }, index=[0]), sort=False)

        df = df.sort_values(by = 'SWalign', ascending=False)
        return df[:30]


def retrieve_similar_bills(sec_id_txt):
    lid = LID(aligner=AffineLocalAligner())
    sec_id, sec_txt = sec_id_txt
    df = lid.find_alignment(sec_txt, sec_id)
    del lid

    return df
    

def main():
    #FILE_NAME = "PPACA_final_version_sec_dict.pkl.json"
    FILE_NAME = ""
    ppaca_sec_list = []
    parser = argparse.ArgumentParser(description='runs scripts for lid system')
    parser.add_argument('--p', dest='data_path', help="file path of bill data to be searched")
    parser.add_argument('--i', dest='numb', help="file path of bill data to be searched")

    args = parser.parse_args()    

    column_names = ['luceneScore', 'SWalign', 'billSecidA', 'textA', 'billAstart', 'billAend', 'billSecidB','textB', 'billBstart', 'billBend']
    total_df = pd.DataFrame(columns = column_names)

    with open(args.data_path + FILE_NAME ,'r') as json_file:
        json_lines = list(json_file)
        num_files = 1
        start = time.time()
        for json_str in json_lines:
            data = json.loads(json_str)
            if 'section_id' not in data:
                continue

            lim = 20000
            if (len(data['section_txt']) > lim):
                data['section_txt'] = data['section_txt'][:lim]

            doc = (data['section_id'], data['section_txt'])
        
            total_df = total_df.append(retrieve_similar_bills(doc), ignore_index=True)
            if num_files % 200 == 0 and num_files > 0:
                total_df.to_csv('output/sec_to_sec' + '_' + str(args.numb) + '_' + str(num_files) + '.csv')
                total_df.to_pickle('output/sec_to_sec' + '_' + str(args.numb) + '_' + str(num_files) + '.pkl')
                total_df = total_df.iloc[0:0]

            if num_files % 10 == 0 and num_files > 0:
                now = time.time()
                avg_time = (now-start) / num_files
                print("%d files processed. Average time taken: %f" % (num_files, avg_time))

            num_files += 1
        total_df.to_csv('sec_to_sec' + str(num_files) + '.csv')
        total_df.to_pickle('sec_to_sec' + str(num_files) + '.pkl')
            # ppaca_sec_list = list(data['111_(h,,3590)']['sections']['111_(h,,3590)_enr'].items())
    
    # We may try parallelism alter.
    # try:
    #     pool = Pool(processes = 7)
    #     # results = pool.map(retrieve_similar_bills, ppaca_sec_list)
    #     results = list(tqdm(pool.imap(retrieve_similar_bills, ppaca_sec_list), total=len(ppaca_sec_list)))
    #     print(results)
    # except KeyboardInterrupt:
    #     print "TERMINATE"
    #     pool.terminate()
    #     pool.join()
    #     print "JOINED"



    # for idx, doc in tqdm(enumerate(ppaca_sec_list), desc="iterate over ppaca"):
    #     total_df = total_df.append(retrieve_similar_bills(doc), ignore_index=True)
    #     if idx % 50 == 0:
    #         total_df.to_csv('sec_to_sec.csv')
    #         total_df.to_pickle('sec_to_sec.pkl')
    # total_df.to_csv('sec_to_sec.csv')
    # total_df.to_pickle('sec_to_sec.pkl')

    
    # More robust search should be done here.


if __name__ == "__main__":
    main()
