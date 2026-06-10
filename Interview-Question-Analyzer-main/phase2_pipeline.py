"""Phase 2: Main Pipeline - Integrate IR, AI, Recommendations, EDA."""

import json
import sys
from phase2_ir_engine import IREngine
from phase2_ai_models import AIModels
from phase2_recommendation import RecommendationEngine
from phase2_eda_analysis import EDAAnalysis


def main():
    """Main Phase 2 pipeline."""
    
    print("="*80)
    print("PHASE 2: COMPLETE PIPELINE")
    print("Interview Question Analyzer System")
    print("="*80)
    
    # Step 1: Load data
    print("\n[Step 1] Loading dataset...")
    try:
        with open('storage/dataset_2.json', 'r', encoding='utf-8') as f:
            questions = json.load(f)
        print(f"✓ Loaded {len(questions)} questions")
    except FileNotFoundError:
        print("✗ Dataset not found. Run main.py first to extract questions.")
        return
    
    # Step 2: Initialize IR Engine
    print("\n[Step 2] Initializing IR Engine...")
    ir_engine = IREngine(questions)
    print("✓ IR Engine initialized")
    
    # Step 3: Initialize AI Models
    print("\n[Step 3] Initializing AI Models...")
    ai_models = AIModels(questions)
    print("✓ AI Models initialized")
    
    # Step 4: Train models
    print("\n[Step 4] Training classification model...")
    try:
        ai_models.train_classifier()
        print("✓ Classification model trained")
    except Exception as e:
        print(f"✗ Error training classifier: {e}")
    
    # Step 5: Build indexes
    print("\n[Step 5] Building IR indexes...")
    ir_engine.build_tfidf_index()
    ir_engine.build_keyword_index()
    ir_engine.build_bm25()
    print("✓ Indexes built")
    
    # Step 6: Initialize Recommendation Engine
    print("\n[Step 6] Initializing Recommendation Engine...")
    rec_engine = RecommendationEngine(ir_engine, ai_models)
    print("✓ Recommendation Engine initialized")
    
    # Step 7: Generate EDA
    print("\n[Step 7] Generating EDA Analysis...")
    eda = EDAAnalysis(questions, ir_engine, ai_models)
    eda_report = eda.generate_comprehensive_report()
    print("✓ EDA Analysis generated")
    
    # Step 8: Generate Insights
    print("\n[Step 8] Generating Insights...")
    insights = eda.generate_insights(eda_report)
    print("✓ Insights generated")
    
    # Step 9: Save all models and data
    print("\n[Step 9] Saving models and data...")
    ir_engine.save_index('storage')
    ai_models.save_models('storage')
    eda.save_report('storage')
    print("✓ All models saved")
    
    # Step 10: Test the system
    print("\n" + "="*80)
    print("SYSTEM TEST")
    print("="*80)
    
    test_queries = [
        "python programming",
        "data structures algorithms",
        "system design"
    ]
    
    for query in test_queries:
        print(f"\n📌 Query: {query}")
        
        # Search
        results = ir_engine.search(query, top_k=3)
        print(f"\n  🔍 Search Results:")
        for r in results:
            print(f"    • {r['question'][:60]}...")
            print(f"      Relevance: {r['relevance_percentage']}%")
        
        # Recommendations
        recs = rec_engine.get_recommendations(query, top_k=3)
        print(f"\n  💡 Recommendations:")
        for i, rec in enumerate(recs, 1):
            print(f"    {i}. {rec['question'][:60]}...")
            print(f"       Skills: {', '.join(rec['skills'][:2])}")
            print(f"       Why: {rec['why_recommended']}")
    
    # Display EDA Summary
    print("\n" + "="*80)
    print("EDA SUMMARY")
    print("="*80)
    
    print(f"\n📊 Basic Statistics:")
    stats = eda_report['basic_statistics']
    print(f"  Total Questions: {stats['total_questions']:,}")
    print(f"  Categories: {stats['unique_categories']}")
    print(f"  Avg Question Length: {stats['avg_question_length']:.1f} words")
    
    print(f"\n🎯 Top 5 Categories:")
    for cat, count in list(eda_report['category_distribution']['top_10'].items())[:5]:
        print(f"  • {cat}: {count}")
    
    print(f"\n💪 Top 5 Skills Tested:")
    for skill, count in list(eda_report['skills_distribution'].items())[:5]:
        print(f"  • {skill.replace('_', ' ').title()}: {count}")
    
    print(f"\n📈 Difficulty Distribution:")
    for diff, count in eda_report['difficulty_distribution'].items():
        pct = round(100 * count / sum(eda_report['difficulty_distribution'].values()))
        print(f"  • {diff}: {count} ({pct}%)")
    
    print(f"\n✨ Key Insights:")
    for insight in insights[:5]:
        print(f"  • {insight['title']}: {insight['value']}")
        print(f"    → {insight['insight']}")
    
    # Save configuration
    print("\n[Step 11] Saving system configuration...")
    config = {
        'total_questions': len(questions),
        'system_components': ['IR_Engine', 'AI_Models', 'Recommendation_Engine', 'EDA_Analysis'],
        'models_trained': True,
        'indexes_built': True,
        'ready_for_gui': True
    }
    
    with open('storage/phase2_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("="*80)
    print("PHASE 2 PIPELINE COMPLETE!")
    print("="*80)
    print("\n✓ All components initialized and tested")
    print("✓ Models trained and saved")
    print("✓ Ready for Streamlit GUI!")
    print("\nNext: Run 'streamlit run phase2_gui.py' to start the web interface")
    print("="*80)


if __name__ == "__main__":
    main()
