# 🧠 AI-Powered CS Course Recommender & Intelligence Dashboard

An intelligent, full-stack web application that scrapes, indexes, and recommends Computer Science courses using NLP-based AI. The system crawls multiple educational platforms in real-time, extracts student reviews, and uses sentiment analysis to generate quality ratings — all served through a modern Flask dashboard.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.x-000000?logo=flask&logoColor=white)
![NLTK](https://img.shields.io/badge/NLP-NLTK_VADER-green)
![Scikit-Learn](https://img.shields.io/badge/ML-Scikit--Learn-F7931E?logo=scikit-learn&logoColor=white)
![Selenium](https://img.shields.io/badge/Scraping-Selenium-43B02A?logo=selenium&logoColor=white)

---

## ✨ Features

### 🔍 Semantic Search Engine
- **TF-IDF Vectorization** with bigram support for context-aware search
- **Cosine Similarity** matching to rank courses by relevance
- Results sorted by **AI Star Rating first**, then by keyword relevance

### ⭐ AI-Powered Rating System
- **NLTK VADER Sentiment Analysis** scores course descriptions and student reviews
- **Platform Prestige Weighting** — courses from MIT, Google, Stanford, and Coursera receive a prestige bonus
- **Review-Weighted Scoring** — when student reviews are available, ratings are 70% based on review sentiment and 30% on description sentiment

### 🕷️ Multi-Platform Web Scraper
- Scrapes **24+ targets** across 5 platforms using headless Chrome (Selenium)
- **Deep Review Scraping** — navigates to individual Coursera course pages to extract real student reviews
- **robots.txt compliant** — respects each site's crawling policies
- **Asynchronous execution** with real-time progress bar in the UI
- Currently targets:
  - **MIT OpenCourseWare** (15 CS topics)
  - **Coursera** (Computer Science, Data Science, IT catalogs)
  - **Cybrary** (AI, Cybersecurity, Cloud, Networking paths)
  - **Khan Academy** (Computer Programming)
  - **CourseTalk** (Course aggregator)

### 💬 NLP Review Summarization
- Extracts up to 10 reviews per course from Coursera's `/reviews` pages
- Uses NLTK tokenization and frequency analysis to identify top-mentioned concepts
- Generates human-readable summaries like: *"Based on 8 reviews, students frequently mention: python, algorithms, data"*

### 🎨 Modern Dashboard UI
- Clean, responsive Flask + Jinja2 frontend
- Course cards with provider badges, star ratings, and review summaries
- Live progress bar during scraping with real-time status updates
- Empty state handling and search clearing

---

## 🧪 How the AI Works

### Rating Pipeline
```
Course Description + Student Reviews
         │
         ▼
┌─────────────────────────┐
│  NLTK VADER Sentiment   │  → compound score [-1, +1]
│  Analysis               │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Weighted Scoring       │  → 70% review sentiment
│  (if reviews exist)     │    30% description sentiment
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Platform Prestige      │  → +0.8 stars for MIT,
│  Bonus                  │    Google, Stanford, Coursera
└─────────────────────────┘
         │
         ▼
      ⭐ 1-5 Star Rating
```

### Search Pipeline
```
User Query → Clean & Tokenize → TF-IDF Vectorize → Cosine Similarity
                                                          │
                                              Sort by Stars (primary)
                                              then Match Score (secondary)
                                                          │
                                                    Top 20 Results
```

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask (Python) |
| **Frontend** | HTML5, CSS3, JavaScript |
| **NLP Engine** | NLTK (VADER Sentiment, Tokenization, Stopwords) |
| **Search Engine** | Scikit-Learn (TF-IDF + Cosine Similarity) |
| **Web Scraping** | Selenium (Headless Chrome) + BeautifulSoup4 |
| **Data Storage** | JSON + Excel (Pandas) |
| **Async Processing** | Python Threading |

---

## 📝 License

This project is for educational purposes.

---

## 👤 Authors

**Marc Zaki, Muhammad Kandil, Retag Ahmed**

---
