"""Phase 2: Recommendation System - Combine IR + AI."""

import json
import numpy as np
from collections import Counter


class RecommendationEngine:
    """Generate intelligent recommendations combining IR + AI."""
    
    def __init__(self, ir_engine, ai_models):
        """Initialize with IR engine and AI models."""
        self.ir_engine = ir_engine
        self.ai_models = ai_models
        self.questions = ai_models.questions
    
    def get_recommendations(self, search_query, user_difficulty="Intermediate", top_k=10):
        """
        Generate recommendations based on search query and user profile.
        
        Args:
            search_query: User's search query
            user_difficulty: User's difficulty level
            top_k: Number of recommendations to return
        
        Returns:
            List of recommended questions with reasoning
        """
        
        # Step 1: Get search results (IR)
        search_results = self.ir_engine.search(search_query, top_k=20, method='hybrid')
        
        if not search_results:
            return []
        
        # Step 2: Analyze search query to extract features
        query_analysis = {
            'skills': self.ai_models.extract_skills(search_query),
            'difficulty': self.ai_models.estimate_difficulty(search_query)['difficulty']
        }
        
        # Step 3: Score and filter results
        scored_results = []
        
        for result in search_results:
            question_data = self.questions[result['id'] - 1]
            
            # Analyze the result question
            q_analysis = {
                'skills': self.ai_models.extract_skills(question_data['question']),
                'difficulty': self.ai_models.estimate_difficulty(question_data['question'])['difficulty'],
                'category': f"{question_data['main_category']} > {question_data['sub_category']}"
            }
            
            # Calculate scoring factors
            
            # 1. Relevance (from IR)
            relevance_score = result['relevance_percentage'] / 100
            
            # 2. Difficulty fit
            difficulty_progression = self._calc_difficulty_fit(
                query_analysis['difficulty'],
                q_analysis['difficulty'],
                user_difficulty
            )
            
            # 3. Skill relevance
            skill_relevance = self._calc_skill_relevance(
                query_analysis['skills'],
                q_analysis['skills']
            )
            
            # 4. Diversity bonus
            diversity_bonus = 0.1  # Encourage some variety
            
            # Combine scores
            final_score = (
                0.5 * relevance_score +
                0.2 * difficulty_progression +
                0.2 * skill_relevance +
                0.1 * diversity_bonus
            )
            
            scored_results.append({
                'id': result['id'],
                'question': question_data['question'],
                'category': q_analysis['category'],
                'skills': q_analysis['skills'],
                'difficulty': q_analysis['difficulty'],
                'relevance': result['relevance_percentage'],
                'score': final_score,
                'why_recommended': self._generate_recommendation_reason(
                    relevance_score,
                    difficulty_progression,
                    skill_relevance,
                    query_analysis,
                    q_analysis
                )
            })
        
        # Step 4: Sort by score and remove duplicates by category
        scored_results.sort(key=lambda x: -x['score'])
        
        # De-duplicate by category (only 1 per category in top results)
        seen_categories = set()
        final_recommendations = []
        
        for result in scored_results:
            if result['category'] not in seen_categories:
                final_recommendations.append(result)
                seen_categories.add(result['category'])
            
            if len(final_recommendations) >= top_k:
                break
        
        return final_recommendations
    
    def _calc_difficulty_fit(self, query_difficulty, question_difficulty, user_difficulty):
        """Calculate how well question difficulty fits user level."""
        
        difficulty_levels = {'Beginner': 1, 'Intermediate': 2, 'Advanced': 3}
        
        query_level = difficulty_levels.get(query_difficulty, 2)
        q_level = difficulty_levels.get(question_difficulty, 2)
        user_level = difficulty_levels.get(user_difficulty, 2)
        
        # Ideal progression: slightly above user level but related to query
        ideal_level = user_level + 1
        
        # Penalize if too far from ideal
        distance = abs(q_level - ideal_level)
        
        if distance == 0:
            return 1.0
        elif distance == 1:
            return 0.8
        else:
            return 0.5
    
    def _calc_skill_relevance(self, query_skills, question_skills):
        """Calculate skill relevance between query and question."""
        
        if not query_skills or not question_skills:
            return 0.5
        
        # Common skills
        common = set(query_skills) & set(question_skills)
        total = set(query_skills) | set(question_skills)
        
        if not total:
            return 0.5
        
        jaccard_similarity = len(common) / len(total)
        
        return jaccard_similarity
    
    def _generate_recommendation_reason(self, relevance, difficulty_fit, skill_relevance, query_analysis, question_analysis):
        """Generate human-readable recommendation reason."""
        
        reasons = []
        
        if relevance > 0.8:
            reasons.append("Highly relevant to your search")
        elif relevance > 0.6:
            reasons.append("Related to your search")
        
        if difficulty_fit > 0.8:
            reasons.append("Perfect difficulty progression")
        elif difficulty_fit > 0.5:
            reasons.append("Good difficulty match")
        
        common_skills = set(query_analysis['skills']) & set(question_analysis['skills'])
        if common_skills:
            reasons.append(f"Tests same skills: {', '.join(list(common_skills)[:2])}")
        
        if not reasons:
            reasons.append("Similar problem domain")
        
        return " + ".join(reasons)
    
    def get_learning_path(self, topic, num_questions=10):
        """
        Generate a learning path for a topic.
        
        Returns questions progressing from beginner to advanced.
        """
        
        # Search for topic
        results = self.ir_engine.search(topic, top_k=100)
        
        # Organize by difficulty
        by_difficulty = {'Beginner': [], 'Intermediate': [], 'Advanced': []}
        
        for result in results:
            question_data = self.questions[result['id'] - 1]
            difficulty = self.ai_models.estimate_difficulty(question_data['question'])['difficulty']
            
            by_difficulty[difficulty].append({
                'question': question_data['question'],
                'category': f"{question_data['main_category']} > {question_data['sub_category']}",
                'difficulty': difficulty,
                'relevance': result['relevance_percentage']
            })
        
        # Create progression
        learning_path = []
        
        # Add beginner questions
        learning_path.extend(sorted(by_difficulty['Beginner'], 
                                   key=lambda x: -x['relevance'])[:num_questions//3])
        
        # Add intermediate
        learning_path.extend(sorted(by_difficulty['Intermediate'],
                                   key=lambda x: -x['relevance'])[:num_questions//3])
        
        # Add advanced
        learning_path.extend(sorted(by_difficulty['Advanced'],
                                   key=lambda x: -x['relevance'])[:num_questions//3])
        
        return learning_path[:num_questions]
    
    def get_category_recommendations(self, category):
        """Get recommendations within a specific category."""
        
        category_questions = [
            q for q in self.questions 
            if f"{q['main_category']} > {q['sub_category']}" == category
        ]
        
        # Analyze and score
        recommendations = []
        
        for q in category_questions[:50]:  # Limit to 50
            analysis = {
                'question': q['question'],
                'category': category,
                'difficulty': self.ai_models.estimate_difficulty(q['question'])['difficulty'],
                'skills': self.ai_models.extract_skills(q['question']),
            }
            recommendations.append(analysis)
        
        # Sort by difficulty
        difficulty_order = {'Beginner': 0, 'Intermediate': 1, 'Advanced': 2}
        recommendations.sort(key=lambda x: difficulty_order.get(x['difficulty'], 1))
        
        return recommendations


# Main execution
if __name__ == "__main__":
    print("Recommendation System test - run after IR Engine and AI Models are initialized")
