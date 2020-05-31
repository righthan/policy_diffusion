# Purpose

In U.S. Federal Legislation, we are aiming at understanding the complicated nature of U.S. politics based on ML approach on a network between bills(sections) and political entities(congressmen, lobbyists). As the first step toward this goal, we consider it important to build a reference network between bills (or sections), in which an edge indicates one section likely refers to another. However, the current approaches are not scalable owing to its slow speed when calculating the lexical similarity between texts. To resolve this issue and claim that the improvement is truly made, we utlize [Legislative Influence Detector](http://www.dssgfellowship.org/lid/) (henceforth, LID) to generate a network of ground truth. 

# LID

(Originally [here](https://github.com/dssg/policy_diffusion))
LID uses the Smith-Waterman local-alignment algorithm to find matching text across documents. This algorithm grabs pieces of text from each document and compares each word, adding points for matches and subtracting points for mismatches. Unfortunately, the local-alignment algorithm is **too slow** for large sets of text, such as ours. It could take the algorithm thousands of years to finish analyzing the legislation. We improved the speed of the analysis by first limiting the number of documents that need to be compared. Elasticsearch, our database of choice for this project, efficiently calculates Lucene scores. When we use LID to search for a document, it quickly compares our document against all others and grabs the N most similar documents as measured by their Lucene scores. Then we run the local-alignment algorithm on those N. (N can be set arbitrarily.)

## How to use?

* Install [Elasticsearch](https://www.elastic.co/). (Free!)
* Put your data in elasticsearch. This [link](https://www.elastic.co/guide/en/elasticsearch/reference/current/getting-started-index.html#getting-started-batch-processing) would help.
* Run `lid.py` with `Python 3.x` after setting IP and port to elasticsearch.

## Important Directories and Files

* `lid.py` : Main code. To find the best matching sections given a text, using both Smith-Waterman local-alignment algorithm and Elasticsearch.
  * This file may be modified to accomodate different data format.
* `text_alignment.py` : This contains LID's implementation of the smith-waterman algorithm.
  * Note that two different algorithms are implemented as a class: `LocalAligner`, `AffineLocalAligner`
  * Scores are updated according to the [AJPS paper by John Wilkerson et al.](https://onlinelibrary.wiley.com/doi/full/10.1111/ajps.12175)
* `database.py` : Elasticsearch engine is implemented. (Inverted index search)
* `utils/test_cleaning.py` : For fair comparison between texts, the redundant parts are processed.
* `_not_in_use/` : Folder and files are moved to this directory unless they are needed to build a network for our main goal.

## Note
The python codes are originally implemented with `Python 2.x`, thus the compatibility issues may arise. 