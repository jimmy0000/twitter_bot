from __future__ import division
"""
    Rocchio-like classifier
    
    http://nlp.stanford.edu/IR-book/pdf/14vcat.pdf
    
    The basic idea here is to represent each document as a vector of counts 
    of ngrams.
    
        - The vectors are normalized to length 1
        - Centroids are calculated for the positive training documents and 
          negative training documents
        - New documents are classified by which of the two centroids they
          are closer to.
        - In the current implementation, the distance measure is cosine.
    
    This does not seem to be well-suited to tweet classification as the
    vectors are all sparse with element values rarely greater than 1.

"""
import math
import preprocessing

EPSILON = 1.0e-6

class RocchioClassifier:
    
    # Precision = 0.936, Recall = 0.606, F1 = 0.736
    weight_bigrams = 2.0318
    weight_trigrams = 4.4337
    threshold = 1.9442

    @staticmethod
    def set_params(weight_bigrams, weight_trigrams, threshold):
        
        RocchioClassifier.weight_bigrams = weight_bigrams
        RocchioClassifier.weight_trigrams = weight_trigrams   
        RocchioClassifier.threshold = threshold  

    @staticmethod    
    def get_params():
        return (
            RocchioClassifier.weight_bigrams, 
            RocchioClassifier.weight_trigrams,   
            RocchioClassifier.threshold
        )
    
    @staticmethod    
    def get_param_names(): 
        return (
            'weight_bigrams',
            'weight_trigrams',
            'threshold'
        )
        
    @staticmethod
    def get_weights():
        weights = {
            1 : 1.0, 
            2 : RocchioClassifier.weight_bigrams, 
            3 : RocchioClassifier.weight_trigrams
        }
        total = sum(weights.values())
        return dict((n,w/total) for n,w in weights.items())     
    
    @staticmethod
    def build_inv_index(documents):
        """Build an inverted index of the documents.
            inv_index[word][i] = number of occurences of word in documents[i]
        """
        
        inv_index = {}
  
        for i,doc in enumerate(documents):
            for word in doc:
                if not word in inv_index.keys():
                    inv_index[word] = {}
        return inv_index
       
    @staticmethod
    def compute_tfidf(documents):
        """Build a tf-idf dict for documents
            tfidf[word][i] = tf-idf for word and document with index i
        """
        
        inv_index = RocchioClassifier.build_inv_index(documents)
       
        tfidf = {}
        logN = math.log(len(documents), 10)
        for word in inv_index:
            # word_doc_counts[i] = number of occurences of word in documents[i]
            word_doc_counts = inv_index[word] 
            # inverse document frequency ~ -log10(number of documents that word occurs in)
            idf = logN - math.log(len(word_doc_counts), 10)
            for doc_idx,word_count in word_doc_counts.items():
                if word not in tfidf:
                    tfidf[word] = {}
                # term frequency ~ log10(number of occurrences of word in doc)    
                tf = 1.0 + math.log(word_count, 10)
                tfidf[word][doc_idx] = tf * idf 
       
        # Calculate per-document l2 norms for use in cosine similarity
        # tfidf_l2norm[d] = sqrt(sum[tdidf**2])) for tdidf of all words in 
        # document number d
        tfidf_l2norm2 = {}
        for word, doc_indexes in tfidf.items():
            for doc_idx,val in doc_indexes.items():
                tfidf_l2norm2[doc_idx] = tfidf_l2norm2.get(doc_idx, 0.0) + val ** 2
        tfidf_l2norm = dict((doc_idx,math.sqrt(val)) for doc_idx,val in tfidf_l2norm2.items())   

        return tfidf, tfidf_l2norm
    
    @staticmethod
    def get_centroid(vocabulary, documents):
        tfidf,tfidf_l2norm = RocchioClassifier.compute_tfidf(documents)
    
        N = len(documents)
        return dict((word, sum(tfidf[word])/N) for word in tfidf)
 
        def get_normalized_sum(word):
            if word not in tfidf: 
                return 0.0
            return sum(tfidf[word][doc_idx]/tfidf_l2norm[doc_idx] for doc_idx in tfidf[word] if tfidf[word][doc_idx]) 
        
        return dict((word, get_normalized_sum(word)/N) for word in vocabulary)
        
    @staticmethod
    def get_query_vec(ngrams):
        # Construct the query vector as a dict word:log(tf)
        query_vec = {}
        for word in ngrams: 
            query_vec[word] = query_vec.get(word,0) + 1
        return dict((word, math.log(query_vec[word], 10) + 1.0) for word in query_vec)
        
    @staticmethod
    def get_distance(centroid, query_vec):
        # Return the distance between query_vec and centroid
        centroid_vec = dict((word, centroid.get(word,0.0)) for word in query_vec)  
        # Return the cosine    
        # ~!@# Assume some normalization somewhere
        return sum(query_vec[word] * centroid_vec[word] for word in query_vec)    
    
    def __init__(self, training_data):
        """RocchioClassifier initialization
        """
        self.pos_documents = dict((n,[]) for n in (1,2,3))
        self.neg_documents = dict((n,[]) for n in (1,2,3))
        self.vocab = dict((n,set()) for n in (1,2,3))
        self.pos_centroid = dict((n,{}) for n in (1,2,3))
        self.neg_centroid = dict((n,{}) for n in (1,2,3))
       
        self.train(training_data)
        
    def __repr__(self):
        
        def show_pos_neg(n, vocab, pos_centroid, neg_centroid):
            def pn(word):
                p = pos_centroid.get(word, 0.0)
                n = neg_centroid.get(word, 0.0)
                return '%6.4f - %6.4f = %7.4f %s' % (p, n, p-n, word)
            def order(word):
                return neg_centroid.get(word, 0.0) - pos_centroid.get(word, 0.0)
            return 'pos neg n=%d\n%s' % (n, '\n'.join(pn(word) for word in sorted(vocab, key = order)))
        
        return '\n'.join(show_pos_neg(n, self.vocab[n], self.pos_centroid[n], self.neg_centroid[n]) 
            for n in (3,2,1)) 

    def _add_example(self, cls, message):
        """Add a training example
        """

        words = preprocessing.extract_words(message)
        if not words:
            return
  
        documents = self.pos_documents if cls else self.neg_documents
        
        for n in (1,2,3):
            ngrams = preprocessing.get_ngrams(n, words)
            documents[n].append(ngrams)
            for g in ngrams:
                self.vocab[n].add(g)
 
    def train(self, training_data):
        for cls,message in training_data:
            self._add_example(cls, message)
            
        for n in (1,2,3):
            self.pos_centroid[n] = RocchioClassifier.get_centroid(self.vocab[n], self.pos_documents[n])
            self.neg_centroid[n] = RocchioClassifier.get_centroid(self.vocab[n], self.neg_documents[n])

    def classify(self, message, detailed=False):
        """ 
            'message' is a string to classify. Return True or False classification.
            
            Method is to calculate a log_odds from a liklihood based on
            trigram, bigram and unigram (p,n) counts in the training set
            For each trigram
                return smoothed trigram score if trigram in training set, else
                for the 2 bigrams in the trigram
                    return smoothed bigram score if bigram in training set, else
                    for the 2 unigrams in the bigram
                        return smoothed unigram score
                        
            get_score() shows the smoothed scoring    
            <n>gram_score() shows the backoff and smoothing factors    
        """

        words = preprocessing.extract_words(message)
        if not words:
            return False, 0.0
        
        # Best intuition would be to compute back-off based on counts
        ngrams = dict((n,preprocessing.get_ngrams(n, words)) for n in (1,2,3))
        
        query_vecs = dict((n, RocchioClassifier.get_query_vec(ngrams[n])) for n in (1,2,3))
    
        weights = RocchioClassifier.get_weights()   
        
                    
        def get_weighted_distance(centroid):
            return sum(RocchioClassifier.get_distance(centroid[n], query_vecs[n]) * weights[n] for n in (1,2,3))

        pos_distance = get_weighted_distance(self.pos_centroid)
        neg_distance = get_weighted_distance(self.neg_centroid)

        diff = (pos_distance + EPSILON)/(neg_distance + EPSILON)
        return diff > RocchioClassifier.threshold, math.log(diff)

if __name__ == '__main__':
    # Just dump the RocchioClassifier class to stdout  
    for k in sorted(RocchioClassifier.__dict__):
        print '%20s : %s' % (k, BayesClassifier.__dict__[k])
    
