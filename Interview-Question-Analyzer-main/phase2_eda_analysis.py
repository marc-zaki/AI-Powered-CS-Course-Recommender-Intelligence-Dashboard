"""Phase 2: EDA Analysis - Statistics, Visualizations, Insights."""

import json
import numpy as np
from collections import Counter
import os


class EDAAnalysis:
    """Exploratory Data Analysis for interview questions."""
    
    def __init__(self, questions_data, ir_engine, ai_models):
        """Initialize EDA with questions data."""
        self.questions = questions_data if isinstance(questions_data, list) else self._load_json(questions_data)
        self.ir_engine = ir_engine
        self.ai_models = ai_models
    
    def _load_json(self, filepath):
        """Load JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # ========== BASIC STATISTICS ==========
    
    def get_basic_statistics(self):
        """Get basic dataset statistics."""
        
        return {
            'total_questions': len(self.questions),
            'unique_categories': len(set([
                f"{q['main_category']} > {q['sub_category']}"
                for q in self.questions
            ])),
            'unique_main_categories': len(set([q['main_category'] for q in self.questions])),
            'avg_question_length': np.mean([len(q['question'].split()) for q in self.questions]),
            'median_question_length': np.median([len(q['question'].split()) for q in self.questions]),
            'min_question_length': min([len(q['question'].split()) for q in self.questions]),
            'max_question_length': max([len(q['question'].split()) for q in self.questions]),
        }
    
    # ========== CATEGORY ANALYSIS ==========
    
    def get_category_distribution(self):
        """Get distribution of questions by category."""
        
        categories = {}
        
        for q in self.questions:
            cat = f"{q['main_category']} > {q['sub_category']}"
            categories[cat] = categories.get(cat, 0) + 1
        
        # Sort by count
        sorted_cats = sorted(categories.items(), key=lambda x: -x[1])
        
        return {
            'total_categories': len(categories),
            'distribution': dict(sorted_cats),
            'top_10': dict(sorted_cats[:10]),
            'bottom_10': dict(sorted_cats[-10:])
        }
    
    def get_main_category_distribution(self):
        """Get distribution by main category."""
        
        main_categories = {}
        
        for q in self.questions:
            cat = q['main_category']
            main_categories[cat] = main_categories.get(cat, 0) + 1
        
        sorted_cats = sorted(main_categories.items(), key=lambda x: -x[1])
        
        return dict(sorted_cats)
    
    # ========== DIFFICULTY ANALYSIS ==========
    
    def get_difficulty_distribution(self):
        """Get distribution of question difficulties."""
        
        difficulties = {'Beginner': 0, 'Intermediate': 0, 'Advanced': 0}
        
        for q in self.questions:
            difficulty = self.ai_models.estimate_difficulty(q['question'])['difficulty']
            difficulties[difficulty] += 1
        
        return difficulties
    
    # ========== SKILLS ANALYSIS ==========
    
    def get_skills_distribution(self):
        """Get distribution of skills across questions."""
        
        all_skills = []
        
        for q in self.questions:
            skills = self.ai_models.extract_skills(q['question'])
            all_skills.extend(skills)
        
        skill_counts = Counter(all_skills)
        
        return dict(skill_counts.most_common(30))
    
    # ========== KEYWORD ANALYSIS ==========
    
    def get_top_keywords(self, top_n=50):
        """Get most frequent keywords."""
        
        return self.ir_engine.get_keyword_frequency(top_n)
    
    # ========== SENTIMENT ANALYSIS ==========
    
    def get_sentiment_distribution(self):
        """Get distribution of question sentiments (sample)."""
        
        sentiments = {'Positive': 0, 'Neutral': 0, 'Negative': 0}
        
        # Sample 500 questions for speed
        sample_size = min(500, len(self.questions))
        sample_questions = np.random.choice(self.questions, sample_size, replace=False)
        
        for q in sample_questions:
            sentiment = self.ai_models.analyze_sentiment(q['question'])['label']
            sentiments[sentiment] += 1
        
        return sentiments
    
    # ========== COMPREHENSIVE REPORT ==========
    
    def generate_comprehensive_report(self):
        """Generate comprehensive EDA report."""
        
        print("[EDAAnalysis] Generating comprehensive report...")
        
        report = {
            'basic_statistics': self.get_basic_statistics(),
            'category_distribution': self.get_category_distribution(),
            'main_category_distribution': self.get_main_category_distribution(),
            'difficulty_distribution': self.get_difficulty_distribution(),
            'skills_distribution': self.get_skills_distribution(),
            'top_keywords': self.get_top_keywords(50),
        }
        
        print("[EDAAnalysis] Report generated successfully")
        
        return report
    
    # ========== INSIGHTS GENERATION ==========
    
    def generate_insights(self, report=None):
        """Generate actionable insights from data."""
        
        if report is None:
            report = self.generate_comprehensive_report()
        
        insights = []
        
        # Insight 1: Question volume
        total = report['basic_statistics']['total_questions']
        insights.append({
            'title': 'Dataset Size',
            'value': f"{total:,} questions",
            'insight': 'Large and comprehensive interview question database'
        })
        
        # Insight 2: Category coverage
        categories = report['basic_statistics']['unique_categories']
        insights.append({
            'title': 'Category Coverage',
            'value': f"{categories} categories",
            'insight': 'Diverse coverage across multiple interview domains'
        })
        
        # Insight 3: Most common topic
        top_cat = list(report['category_distribution']['top_10'].items())[0]
        insights.append({
            'title': 'Most Tested Topic',
            'value': f"{top_cat[0]} ({top_cat[1]} questions)",
            'insight': 'This is the most frequently tested category in interviews'
        })
        
        # Insight 4: Difficulty distribution
        difficulties = report['difficulty_distribution']
        total_analyzed = sum(difficulties.values())
        if total_analyzed > 0:
            beginner_pct = round(100 * difficulties['Beginner'] / total_analyzed)
            insights.append({
                'title': 'Difficulty Breakdown',
                'value': f"{beginner_pct}% Beginner-friendly questions",
                'insight': 'Good mix of difficulty levels for interview prep'
            })
        
        # Insight 5: Top skills
        skills = report['skills_distribution']
        top_skill = list(skills.items())[0]
        insights.append({
            'title': 'Top Skill Tested',
            'value': f"{top_skill[0].replace('_', ' ').title()}",
            'insight': f"Most frequently tested skill across {top_skill[1]} questions"
        })
        
        # Insight 6: Question length
        avg_length = report['basic_statistics']['avg_question_length']
        insights.append({
            'title': 'Average Question Length',
            'value': f"{avg_length:.1f} words",
            'insight': 'Questions are concise and focused'
        })
        
        return insights
    
    # ========== DATA FOR VISUALIZATIONS ==========
    
    def get_visualization_data(self):
        """Get data formatted for visualizations."""
        
        report = self.generate_comprehensive_report()
        
        viz_data = {
            # Bar chart: Category distribution (top 15)
            'category_bar': {
                'labels': [cat.split(' > ')[-1][:20] for cat in list(report['category_distribution']['top_10'].keys())],
                'values': list(report['category_distribution']['top_10'].values())
            },
            
            # Pie chart: Main categories
            'main_category_pie': {
                'labels': list(report['main_category_distribution'].keys()),
                'values': list(report['main_category_distribution'].values())
            },
            
            # Pie chart: Difficulty
            'difficulty_pie': {
                'labels': list(report['difficulty_distribution'].keys()),
                'values': list(report['difficulty_distribution'].values())
            },
            
            # Bar chart: Top skills
            'skills_bar': {
                'labels': [s.replace('_', ' ').title() for s in list(report['skills_distribution'].keys())[:10]],
                'values': list(report['skills_distribution'].values())[:10]
            },
            
            # Word cloud data: Keywords
            'keywords': report['top_keywords']
        }
        
        return viz_data
    
    # ========== SAVE REPORTS ==========
    
    def save_report(self, output_dir='storage'):
        """Save EDA report to files."""
        
        print(f"[EDAAnalysis] Saving reports to {output_dir}...")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate all reports
        basic_stats = self.get_basic_statistics()
        category_dist = self.get_category_distribution()
        difficulty_dist = self.get_difficulty_distribution()
        skills_dist = self.get_skills_distribution()
        insights = self.generate_insights()
        viz_data = self.get_visualization_data()
        
        # Save as JSON
        report_data = {
            'basic_statistics': basic_stats,
            'category_distribution': category_dist,
            'difficulty_distribution': difficulty_dist,
            'skills_distribution': skills_dist,
            'visualization_data': viz_data,
            'insights': insights
        }
        
        with open(f'{output_dir}/eda_report.json', 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"[EDAAnalysis] Report saved to {output_dir}/eda_report.json")
        
        return report_data


# Main execution
if __name__ == "__main__":
    print("EDA Analysis - run as part of main pipeline")
