"""Phase 2: Information Retrieval Engine - TF-IDF, BM25, Search & Indexing."""

import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
from collections import defaultdict, Counter
import os


class IREngine:
    """Information Retrieval Engine for interview questions."""
    
    def __init__(self, questions_data=None):
        """Initialize IR engine with questions dataset."""
        self.questions = []
        self.question_texts = []
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.keyword_index = defaultdict(list)
        self.bm25_scorer = None
        
        if questions_data:
            self.load_questions(questions_data)
    
    def load_questions(self, questions_data):
        """Load questions from dataset."""
        if isinstance(questions_data, str):
            # Load from file
            with open(questions_data, 'r', encoding='utf-8') as f:
                self.questions = json.load(f)
        else:
            # Use provided data
            self.questions = questions_data
        
        # Extract question texts
        self.question_texts = [q.get('question', '') for q in self.questions]
        print(f"[IREngine] Loaded {len(self.questions)} questions")
    
    def preprocess_text(self, text):
        """Preprocess text for search."""
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def build_tfidf_index(self):
        """Build TF-IDF vectorizer and matrix."""
        print("[IREngine] Building TF-IDF index...")
        
        # Preprocess all questions
        processed_texts = [self.preprocess_text(q) for q in self.question_texts]
        
        # Create TF-IDF vectorizer
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            min_df=2,
            max_df=0.8,
            ngram_range=(1, 2),
            stop_words='english'
        )
        
        # Fit and transform
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(processed_texts)
        
        print(f"[IREngine] TF-IDF index built: {self.tfidf_matrix.shape}")
        print(f"[IREngine] Vocabulary size: {len(self.tfidf_vectorizer.get_feature_names_out())}")
    
    def build_keyword_index(self):
        """Build keyword index for fast lookup."""
        print("[IREngine] Building keyword index...")
        
        self.keyword_index = defaultdict(list)
        
        for idx, question in enumerate(self.questions):
            words = self.preprocess_text(question.get('question', '')).split()
            for word in set(words):
                if len(word) > 2:  # Skip short words
                    self.keyword_index[word].append(idx)
        
        print(f"[IREngine] Keyword index built: {len(self.keyword_index)} unique keywords")
    
    def build_bm25(self):
        """Build BM25 scorer for better ranking."""
        print("[IREngine] Building BM25 index...")
        
        try:
            from rank_bm25 import BM25Okapi
            
            # Tokenize all questions
            tokenized_docs = [
                self.preprocess_text(q).split() for q in self.question_texts
            ]
            
            # Create BM25 scorer
            self.bm25_scorer = BM25Okapi(tokenized_docs)
            print("[IREngine] BM25 index built successfully")
        
        except ImportError:
            print("[IREngine] rank_bm25 not installed, skipping BM25")
    
    def search_tfidf(self, query, top_k=10):
        """Search using TF-IDF + cosine similarity."""
        if self.tfidf_matrix is None:
            self.build_tfidf_index()
        
        # Preprocess query
        query_processed = self.preprocess_text(query)
        
        # Vectorize query
        try:
            query_vector = self.tfidf_vectorizer.transform([query_processed])
        except Exception:
            self.build_tfidf_index()
            query_vector = self.tfidf_vectorizer.transform([query_processed])
        
        # Calculate similarity
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:
                results.append({
                    'id': self.questions[idx]['id'],
                    'question': self.questions[idx]['question'],
                    'category': f"{self.questions[idx]['main_category']} > {self.questions[idx]['sub_category']}",
                    'score': float(similarities[idx]),
                    'relevance_percentage': round(similarities[idx] * 100, 1)
                })
        
        return results
    
    def search_bm25(self, query, top_k=10):
        """Search using BM25 ranking."""
        if self.bm25_scorer is None:
            self.build_bm25()
            if self.bm25_scorer is None:
                return []
        
        # Tokenize query
        query_tokens = self.preprocess_text(query).split()
        
        # Score documents
        scores = self.bm25_scorer.get_scores(query_tokens)
        
        # Get top results
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    'id': self.questions[idx]['id'],
                    'question': self.questions[idx]['question'],
                    'category': f"{self.questions[idx]['main_category']} > {self.questions[idx]['sub_category']}",
                    'score': float(scores[idx]),
                    'relevance_percentage': round(min(scores[idx] / 10 * 100, 100), 1)
                })
        
        return results
    
    def search(self, query, top_k=10, method='hybrid'):
        """Search with hybrid approach (TF-IDF + BM25)."""
        
        if method == 'tfidf':
            return self.search_tfidf(query, top_k)
        
        elif method == 'bm25':
            return self.search_bm25(query, top_k)
        
        elif method == 'hybrid':
            # Get results from both methods
            tfidf_results = self.search_tfidf(query, top_k * 2)
            bm25_results = self.search_bm25(query, top_k * 2)
            
            # Combine and re-rank (60% TF-IDF + 40% BM25)
            scores = {}
            
            for r in tfidf_results:
                scores[r['id']] = r['relevance_percentage'] * 0.6
            
            for r in bm25_results:
                scores[r['id']] = scores.get(r['id'], 0) + (r['relevance_percentage'] * 0.4)
            
            # Sort by combined score
            sorted_ids = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
            
            results = []
            for q_id, score in sorted_ids:
                question = self.questions[q_id - 1]  # ID starts from 1
                results.append({
                    'id': question['id'],
                    'question': question['question'],
                    'category': f"{question['main_category']} > {question['sub_category']}",
                    'score': score,
                    'relevance_percentage': round(score, 1)
                })
            
            return results
    
    def find_similar(self, query, top_k=5):
        """Find questions similar to given query."""
        return self.search(query, top_k=top_k, method='tfidf')
    
    def get_keyword_frequency(self, top_n=50):
        """Get most frequent keywords across all questions."""
        all_words = []
        
        for question in self.questions:
            words = self.preprocess_text(question.get('question', '')).split()
            all_words.extend(words)
        
        # Filter out short words
        words = [w for w in all_words if len(w) > 2]
        
        # Count frequency
        word_freq = Counter(words)
        
        return dict(word_freq.most_common(top_n))
    
    def get_statistics(self):
        """Get IR statistics."""
        keyword_freq = self.get_keyword_frequency(50)
        
        return {
            'total_questions': len(self.questions),
            'unique_keywords': len(self.keyword_index),
            'top_keywords': keyword_freq,
            'avg_question_length': np.mean([len(q.split()) for q in self.question_texts]),
        }
    
    def save_index(self, output_dir='storage'):
        """Save index to files."""
        print(f"[IREngine] Saving index to {output_dir}...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        import joblib
        # Save TF-IDF vectorizer
        joblib.dump(self.tfidf_vectorizer, f'{output_dir}/tfidf_vectorizer.pkl')
        
        # Save TF-IDF matrix
        joblib.dump(self.tfidf_matrix, f'{output_dir}/tfidf_matrix.pkl')
        
        # Save BM25 scorer
        if self.bm25_scorer:
            joblib.dump(self.bm25_scorer, f'{output_dir}/bm25_scorer.pkl')
        
        # Save keyword index
        with open(f'{output_dir}/keyword_index.json', 'w') as f:
            json.dump(dict(self.keyword_index), f)
        
        print("[IREngine] Index saved successfully")
    
    def load_index(self, input_dir='storage'):
        """Load index from files."""
        print(f"[IREngine] Loading index from {input_dir}...")
        
        import joblib
        # Load TF-IDF vectorizer
        self.tfidf_vectorizer = joblib.load(f'{input_dir}/tfidf_vectorizer.pkl')
        
        # Load TF-IDF matrix
        self.tfidf_matrix = joblib.load(f'{input_dir}/tfidf_matrix.pkl')
        
        # Load BM25 scorer if exists
        try:
            self.bm25_scorer = joblib.load(f'{input_dir}/bm25_scorer.pkl')
        except FileNotFoundError:
            pass
        
        # Load keyword index
        with open(f'{input_dir}/keyword_index.json', 'r') as f:
            self.keyword_index = defaultdict(list)
            data = json.load(f)
            for k, v in data.items():
                self.keyword_index[k] = v
        
        print("[IREngine] Index loaded successfully")


# Main execution
if __name__ == "__main__":
    print("="*80)
    print("PHASE 2: IR ENGINE")
    print("="*80)
    
    # Load questions
    engine = IREngine('storage/dataset_2.json')
    
    # Build indexes
    print("\nBuilding indexes...")
    engine.build_tfidf_index()
    engine.build_keyword_index()
    engine.build_bm25()
    
    # Get statistics
    stats = engine.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total Questions: {stats['total_questions']}")
    print(f"  Unique Keywords: {stats['unique_keywords']}")
    print(f"  Avg Question Length: {stats['avg_question_length']:.1f} words")
    
    # Test search
    print(f"\nTop Keywords:")
    for word, freq in list(stats['top_keywords'].items())[:10]:
        print(f"  {word}: {freq}")
    
    # Save indexes
    engine.save_index('storage')
    
    # Test search
    print("\n" + "="*80)
    print("TEST SEARCH")
    print("="*80)
    
    test_queries = [
        "python programming",
        "data structures",
        "algorithm optimization"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        results = engine.search(query, top_k=3)
        for r in results:
            print(f"  • {r['question'][:60]}...")
            print(f"    Category: {r['category']}, Relevance: {r['relevance_percentage']}%")
