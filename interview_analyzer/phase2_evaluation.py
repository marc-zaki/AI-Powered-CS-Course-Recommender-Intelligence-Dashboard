"""Phase 2: Evaluation Module - Test performance and quality."""

import json
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import time


class EvaluationModule:
    """Comprehensive evaluation of IR + AI system."""
    
    def __init__(self, ir_engine, ai_models, rec_engine, questions):
        """Initialize evaluation module."""
        self.ir_engine = ir_engine
        self.ai_models = ai_models
        self.rec_engine = rec_engine
        self.questions = questions
        self.results = {}
    
    # ========== IR ENGINE EVALUATION ==========
    
    def evaluate_search_speed(self, num_queries=10):
        """Measure search speed."""
        
        print("[Evaluation] Testing search speed...")
        
        test_queries = [
            "python programming",
            "data structures",
            "algorithms",
            "databases",
            "system design",
            "binary search",
            "hash table",
            "sorting",
            "recursion",
            "dynamic programming"
        ][:num_queries]
        
        times = []
        
        for query in test_queries:
            start = time.time()
            self.ir_engine.search(query, top_k=10)
            times.append(time.time() - start)
        
        avg_time = np.mean(times)
        
        self.results['search_speed'] = {
            'average_ms': round(avg_time * 1000, 2),
            'min_ms': round(min(times) * 1000, 2),
            'max_ms': round(max(times) * 1000, 2),
            'queries_tested': num_queries
        }
        
        print(f"✓ Average search time: {avg_time*1000:.2f}ms")
        return self.results['search_speed']
    
    def evaluate_search_quality(self, num_queries=10):
        """Evaluate search result quality (coverage and diversity)."""
        
        print("[Evaluation] Testing search quality...")
        
        test_queries = [
            "python programming",
            "data structures",
            "algorithms",
            "databases",
            "system design",
            "binary search",
            "hash table",
            "sorting",
            "recursion",
            "dynamic programming"
        ][:num_queries]
        
        quality_metrics = {
            'avg_relevance': 0,
            'unique_categories': 0,
            'top_1_relevance': 0
        }
        
        all_categories = set()
        
        for query in test_queries:
            results = self.ir_engine.search(query, top_k=10)
            
            if results:
                # Track relevance
                relevances = [r['relevance_percentage'] for r in results]
                quality_metrics['avg_relevance'] += np.mean(relevances) / num_queries
                quality_metrics['top_1_relevance'] += relevances[0] / num_queries
                
                # Track category diversity
                for r in results:
                    q = self.questions[r['id'] - 1]
                    cat = f"{q['main_category']} > {q['sub_category']}"
                    all_categories.add(cat)
        
        quality_metrics['unique_categories'] = len(all_categories)
        
        self.results['search_quality'] = quality_metrics
        
        print(f"✓ Average relevance: {quality_metrics['avg_relevance']:.1f}%")
        print(f"✓ Unique categories covered: {quality_metrics['unique_categories']}")
        return quality_metrics
    
    # ========== AI MODELS EVALUATION ==========
    
    def evaluate_classifier_accuracy(self, sample_size=500):
        """Evaluate classifier accuracy on random sample."""
        
        print("[Evaluation] Testing classifier accuracy...")
        
        np.random.seed(42)
        sample_indices = np.random.choice(len(self.questions), min(sample_size, len(self.questions)), replace=False)
        
        correct = 0
        total = 0
        
        for idx in sample_indices:
            q = self.questions[idx]
            predicted_cat = self.ai_models.classify_category(q['question'])
            actual_cat = f"{q['main_category']} > {q['sub_category']}"
            
            if predicted_cat == actual_cat:
                correct += 1
            total += 1
        
        accuracy = correct / total if total > 0 else 0
        
        self.results['classifier_accuracy'] = {
            'accuracy': round(accuracy, 3),
            'correct_predictions': correct,
            'total_tested': total
        }
        
        print(f"✓ Classification accuracy: {accuracy*100:.1f}% ({correct}/{total})")
        return self.results['classifier_accuracy']
    
    def evaluate_skills_extraction(self, sample_size=100):
        """Evaluate skills extraction (coverage)."""
        
        print("[Evaluation] Testing skills extraction...")
        
        np.random.seed(42)
        sample = np.random.choice(self.questions, min(sample_size, len(self.questions)), replace=False)
        
        questions_with_skills = 0
        total_skills = 0
        
        for q in sample:
            skills = self.ai_models.extract_skills(q['question'])
            if skills:
                questions_with_skills += 1
                total_skills += len(skills)
        
        coverage = questions_with_skills / sample_size if sample_size > 0 else 0
        avg_skills = total_skills / questions_with_skills if questions_with_skills > 0 else 0
        
        self.results['skills_extraction'] = {
            'coverage': round(coverage, 3),
            'avg_skills_per_question': round(avg_skills, 2),
            'total_skills_extracted': total_skills,
            'questions_tested': sample_size
        }
        
        print(f"✓ Skills extraction coverage: {coverage*100:.1f}%")
        print(f"✓ Avg skills per question: {avg_skills:.2f}")
        return self.results['skills_extraction']
    
    # ========== RECOMMENDATION EVALUATION ==========
    
    def evaluate_recommendations(self, num_queries=10):
        """Evaluate recommendation quality."""
        
        print("[Evaluation] Testing recommendations...")
        
        test_queries = [
            "python programming",
            "data structures",
            "algorithms",
            "databases",
            "system design",
            "binary search",
            "hash table",
            "sorting",
            "recursion",
            "dynamic programming"
        ][:num_queries]
        
        rec_metrics = {
            'avg_diversity': 0,
            'avg_relevance': 0,
            'avg_recommendations': 0
        }
        
        for query in test_queries:
            recs = self.rec_engine.get_recommendations(query, top_k=10)
            
            if recs:
                # Track diversity
                categories = set([r['category'] for r in recs])
                diversity = len(categories) / len(recs)
                rec_metrics['avg_diversity'] += diversity / num_queries
                
                # Track relevance
                relevances = [r['relevance'] for r in recs]
                rec_metrics['avg_relevance'] += np.mean(relevances) / num_queries
                
                rec_metrics['avg_recommendations'] += len(recs) / num_queries
        
        self.results['recommendations'] = rec_metrics
        
        print(f"✓ Recommendation diversity: {rec_metrics['avg_diversity']:.2f}")
        print(f"✓ Avg recommendation relevance: {rec_metrics['avg_relevance']:.1f}%")
        return rec_metrics
    
    # ========== SYSTEM PERFORMANCE ==========
    
    def evaluate_system_performance(self):
        """Evaluate overall system performance."""
        
        print("[Evaluation] Testing system performance...")
        
        # Memory usage estimate
        import sys
        questions_size = sys.getsizeof(self.questions)
        
        perf = {
            'total_questions': len(self.questions),
            'question_data_size_mb': round(questions_size / (1024**2), 2),
            'unique_categories': len(set([
                f"{q['main_category']} > {q['sub_category']}"
                for q in self.questions
            ]))
        }
        
        self.results['system_performance'] = perf
        
        print(f"✓ Total questions: {perf['total_questions']:,}")
        print(f"✓ Data size: {perf['question_data_size_mb']} MB")
        return perf
    
    # ========== RUN FULL EVALUATION ==========
    
    def run_full_evaluation(self):
        """Run complete evaluation suite."""
        
        print("="*80)
        print("PHASE 2 SYSTEM EVALUATION")
        print("="*80)
        
        # Run all evaluations
        self.evaluate_search_speed()
        self.evaluate_search_quality()
        self.evaluate_classifier_accuracy()
        self.evaluate_skills_extraction()
        self.evaluate_recommendations()
        self.evaluate_system_performance()
        
        # Generate report
        report = self._generate_report()
        
        print("\n" + "="*80)
        print("EVALUATION COMPLETE")
        print("="*80)
        
        return report
    
    def _generate_report(self):
        """Generate evaluation report."""
        
        report = {
            'summary': {
                'total_evaluations': len(self.results),
                'status': 'PASS' if all(self.results.values()) else 'PARTIAL'
            },
            'detailed_results': self.results
        }
        
        return report
    
    def save_report(self, output_path='storage/evaluation_report.json'):
        """Save evaluation report."""
        
        report = {
            'timestamp': str(np.datetime64('now')),
            'results': self.results
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✓ Report saved to {output_path}")
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print evaluation summary."""
        
        print("\n" + "="*80)
        print("EVALUATION SUMMARY")
        print("="*80)
        
        print("\n🔍 Search Engine:")
        if 'search_speed' in self.results:
            print(f"  • Average Search Time: {self.results['search_speed']['average_ms']}ms")
        if 'search_quality' in self.results:
            print(f"  • Average Relevance: {self.results['search_quality']['avg_relevance']:.1f}%")
            print(f"  • Category Diversity: {self.results['search_quality']['unique_categories']}")
        
        print("\n🤖 AI Models:")
        if 'classifier_accuracy' in self.results:
            print(f"  • Classifier Accuracy: {self.results['classifier_accuracy']['accuracy']*100:.1f}%")
        if 'skills_extraction' in self.results:
            print(f"  • Skills Extraction Coverage: {self.results['skills_extraction']['coverage']*100:.1f}%")
        
        print("\n💡 Recommendations:")
        if 'recommendations' in self.results:
            print(f"  • Diversity: {self.results['recommendations']['avg_diversity']:.2f}")
            print(f"  • Average Relevance: {self.results['recommendations']['avg_relevance']:.1f}%")
        
        print("\n📊 System:")
        if 'system_performance' in self.results:
            print(f"  • Total Questions: {self.results['system_performance']['total_questions']:,}")
            print(f"  • Data Size: {self.results['system_performance']['question_data_size_mb']} MB")
        
        print("\n" + "="*80)
