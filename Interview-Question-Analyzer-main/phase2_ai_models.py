"""Phase 2: AI Models - Classification, Sentiment, Skills, Difficulty, Similarity."""

import json
import pickle
import numpy as np
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob
import re
import os


class AIModels:
    """AI Models for question analysis."""
    
    def __init__(self, questions_data=None):
        """Initialize AI models."""
        self.questions = []
        self.classifier_pipeline = None
        self.tfidf_vectorizer = None
        self.categories_list = []
        
        # Skill keywords dictionary
        self.skill_keywords = {
            "programming": ["python", "java", "c++", "javascript", "code", "function", "method", 
                           "class", "object", "variable", "loop", "condition", "syntax"],
            "data_structures": ["array", "list", "tree", "graph", "queue", "stack", "heap",
                               "linked", "node", "pointer", "structure", "hashtable", "trie"],
            "algorithms": ["sort", "search", "binary", "recursion", "dynamic", "greedy",
                          "algorithm", "optimal", "complexity", "efficient", "brute"],
            "database": ["database", "sql", "query", "table", "index", "nosql", "mongodb",
                        "join", "schema", "transaction", "normalization", "aggregate"],
            "system_design": ["system", "design", "architecture", "scale", "distributed",
                             "cache", "load", "server", "client", "network", "protocol"],
            "web": ["web", "http", "api", "rest", "frontend", "backend", "html", "css",
                   "server", "client", "browser", "request", "response"],
            "cloud": ["cloud", "aws", "azure", "gcp", "container", "docker", "kubernetes",
                     "serverless", "lambda", "microservice", "devops"],
            "machine_learning": ["machine", "learning", "neural", "network", "deep",
                                "model", "training", "tensor", "regression", "classification"],
        }
        
        # Difficulty keywords
        self.easy_keywords = ["define", "explain", "describe", "what", "list", "identify",
                             "state", "name", "give", "simple", "basic", "fundamental"]
        self.hard_keywords = ["design", "optimize", "implement", "complex", "advanced",
                             "algorithm", "architecture", "efficient", "scalable", "system"]
        
        if questions_data:
            self.load_questions(questions_data)
    
    def load_questions(self, questions_data):
        """Load questions from dataset."""
        if isinstance(questions_data, str):
            with open(questions_data, 'r', encoding='utf-8') as f:
                self.questions = json.load(f)
        else:
            self.questions = questions_data
        
        # Extract unique categories
        self.categories_list = list(set([
            f"{q['main_category']} > {q['sub_category']}" 
            for q in self.questions
        ]))
        
        print(f"[AIModels] Loaded {len(self.questions)} questions")
        print(f"[AIModels] Found {len(self.categories_list)} categories")
    
    def preprocess_text(self, text):
        """Preprocess text."""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    # ========== MODEL 1: CATEGORY CLASSIFIER ==========
    
    def train_classifier(self):
        """Train category classifier."""
        print("[AIModels] Training category classifier...")
        
        # Prepare data
        X = [q['question'] for q in self.questions]
        y = [f"{q['main_category']} > {q['sub_category']}" for q in self.questions]
        
        # Create pipeline
        self.classifier_pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=2000, ngram_range=(1, 2))),
            ('clf', MultinomialNB())
        ])
        
        # Train
        self.classifier_pipeline.fit(X, y)
        
        # Evaluate on training data
        accuracy = self.classifier_pipeline.score(X, y)
        print(f"[AIModels] Classifier trained - Accuracy: {accuracy:.2%}")
    
    def classify_category(self, question, confidence=False):
        """Classify question into category."""
        if self.classifier_pipeline is None:
            self.train_classifier()
        
        prediction = self.classifier_pipeline.predict([question])[0]
        
        if confidence:
            proba = self.classifier_pipeline.predict_proba([question])[0]
            max_confidence = np.max(proba)
            return {
                'category': prediction,
                'confidence': round(max_confidence, 3)
            }
        
        return {'category': prediction}
    
    # ========== MODEL 2: SKILL EXTRACTOR ==========
    
    def extract_skills(self, question, min_keywords=1):
        """Extract skills from question."""
        text = self.preprocess_text(question)
        
        found_skills = []
        
        for skill, keywords in self.skill_keywords.items():
            count = sum(1 for kw in keywords if kw in text)
            if count >= min_keywords:
                found_skills.append({
                    'skill': skill,
                    'keyword_matches': count
                })
        
        # Sort by matches
        found_skills.sort(key=lambda x: -x['keyword_matches'])
        
        return [s['skill'] for s in found_skills] if found_skills else ['general']
    
    # ========== MODEL 3: DIFFICULTY ESTIMATOR ==========
    
    def estimate_difficulty(self, question):
        """Estimate question difficulty."""
        text = self.preprocess_text(question)
        words = text.split()
        length = len(words)
        
        # Count easy and hard keywords
        easy_count = sum(1 for kw in self.easy_keywords if kw in text)
        hard_count = sum(1 for kw in self.hard_keywords if kw in text)
        
        # Heuristics
        if length < 50 and easy_count > hard_count:
            difficulty = "Beginner"
        elif length > 200 or hard_count > easy_count:
            difficulty = "Advanced"
        else:
            difficulty = "Intermediate"
        
        return {
            'difficulty': difficulty,
            'length': length,
            'easy_indicators': easy_count,
            'hard_indicators': hard_count
        }
    
    # ========== MODEL 4: SENTIMENT ANALYZER ==========
    
    def analyze_sentiment(self, question):
        """Analyze question sentiment."""
        try:
            blob = TextBlob(question)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # Classify
            if polarity > 0.2:
                label = "Positive"
            elif polarity < -0.2:
                label = "Negative"
            else:
                label = "Neutral"
            
            return {
                'polarity': round(polarity, 3),
                'subjectivity': round(subjectivity, 3),
                'label': label
            }
        
        except Exception as e:
            print(f"[AIModels] Sentiment analysis error: {e}")
            return {
                'polarity': 0,
                'subjectivity': 0.5,
                'label': 'Neutral'
            }
    
    # ========== MODEL 5: SIMILARITY ENGINE ==========
    
    def compute_question_embeddings(self):
        """Compute embeddings for all questions."""
        print("[AIModels] Computing question embeddings...")
        
        vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2))
        questions_text = [q['question'] for q in self.questions]
        embeddings = vectorizer.fit_transform(questions_text)
        
        print(f"[AIModels] Embeddings computed: {embeddings.shape}")
        
        return vectorizer, embeddings
    
    def find_similar_questions(self, query, top_k=5):
        """Find similar questions to given query."""
        # Compute embeddings if not done
        if not hasattr(self, '_embeddings'):
            vectorizer, embeddings = self.compute_question_embeddings()
            self._vectorizer = vectorizer
            self._embeddings = embeddings
        else:
            vectorizer = self._vectorizer
            embeddings = self._embeddings
        
        # Vectorize query
        query_vector = vectorizer.transform([query])
        
        # Calculate similarity
        similarities = cosine_similarity(query_vector, embeddings)[0]
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][1:top_k+1]  # Skip first (self)
        
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:
                results.append({
                    'question': self.questions[idx]['question'],
                    'category': f"{self.questions[idx]['main_category']} > {self.questions[idx]['sub_category']}",
                    'similarity': round(similarities[idx], 3)
                })
        
        return results
    
    # ========== COMPREHENSIVE ANALYSIS ==========
    
    def analyze_question_comprehensive(self, question):
        """Comprehensive analysis of a question."""
        analysis = {
            'question': question[:100],
            'category': self.classify_category(question),
            'skills': self.extract_skills(question),
            'difficulty': self.estimate_difficulty(question),
            'sentiment': self.analyze_sentiment(question),
            'similar_questions': self.find_similar_questions(question, top_k=3)
        }
        
        return analysis
    
    def save_models(self, output_dir='storage'):
        """Save trained models."""
        print(f"[AIModels] Saving models to {output_dir}...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save classifier
        if self.classifier_pipeline:
            with open(f'{output_dir}/classifier_model.pkl', 'wb') as f:
                pickle.dump(self.classifier_pipeline, f)
        
        # Save skills dictionary
        with open(f'{output_dir}/skills_keywords.json', 'w') as f:
            json.dump(self.skill_keywords, f)
        
        # Save categories list
        with open(f'{output_dir}/categories_list.json', 'w') as f:
            json.dump(self.categories_list, f)
        
        print("[AIModels] Models saved successfully")
    
    def load_models(self, input_dir='storage'):
        """Load trained models."""
        print(f"[AIModels] Loading models from {input_dir}...")
        
        try:
            with open(f'{input_dir}/classifier_model.pkl', 'rb') as f:
                self.classifier_pipeline = pickle.load(f)
            
            with open(f'{input_dir}/categories_list.json', 'r') as f:
                self.categories_list = json.load(f)
            
            print("[AIModels] Models loaded successfully")
        except FileNotFoundError:
            print("[AIModels] Models not found, will train new ones")


# Main execution
if __name__ == "__main__":
    print("="*80)
    print("PHASE 2: AI MODELS")
    print("="*80)
    
    # Load questions
    models = AIModels('storage/dataset_2.json')
    
    # Train classifier
    print("\nTraining models...")
    models.train_classifier()
    
    # Test analysis
    test_questions = [
        "What is binary search?",
        "Design a distributed caching system",
        "Explain the concept of polymorphism in Python"
    ]
    
    print("\n" + "="*80)
    print("TEST ANALYSIS")
    print("="*80)
    
    for question in test_questions:
        print(f"\nQuestion: {question}")
        analysis = models.analyze_question_comprehensive(question)
        print(f"  Category: {analysis['category']['category']}")
        print(f"  Skills: {', '.join(analysis['skills'])}")
        print(f"  Difficulty: {analysis['difficulty']['difficulty']}")
        print(f"  Sentiment: {analysis['sentiment']['label']}")
        print(f"  Similar Questions:")
        for sim in analysis['similar_questions'][:2]:
            print(f"    • {sim['question'][:60]}... (similarity: {sim['similarity']})")
    
    # Save models
    models.save_models('storage')
