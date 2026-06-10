# 🚀 AI-Powered CS Course Recommender & Intelligence Dashboard

An intelligent, full-stack web application that serves as a comprehensive career and educational companion for Computer Science students and professionals. By merging advanced Large Language Models (LLMs), dynamic data visualization, real-time scraping, and interactive mock interview simulations, the platform acts as a personalized mentor—guiding users from learning new skills to acing technical and behavioral interviews.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.x-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-PyMongo-47A248?logo=mongodb&logoColor=white)
![LLMs](https://img.shields.io/badge/AI-Groq%20%7C%20Gemini-FF6F00?logo=google&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/ML-Scikit--Learn-F7931E?logo=scikit-learn&logoColor=white)
![Selenium](https://img.shields.io/badge/Scraping-Selenium-43B02A?logo=selenium&logoColor=white)

---

## ✨ Exhaustive Feature Breakdown

### 🎓 1. AI-Powered Course Recommender & Study Planner
The core of the educational platform, designed to eliminate the guesswork from upskilling.
- **Skill-Based Recommender Engine:** Users input their current skills and career goals. The AI parses the database to recommend the exact courses required to bridge the gap.
- **Dynamic AI Study Plans:** Generates a custom, week-by-week curriculum and roadmap to help users organize their learning journey based on their availability and targets.
- **User Authentication & Profiles:** Secure session-based login system that tracks user progress, saves their generated study plans, and associates analytics data directly to their profile via MongoDB.

### 🧠 2. The Interview Analyzer (Mock Interview Platform)
A fully integrated, multi-modal interview simulator designed to test both hard algorithmic skills and soft behavioral skills using state-of-the-art LLMs.
- **Generative Search Mode:** Users can search for any CS topic (e.g., "Docker Networking"), and the AI instantly generates relevant theoretical questions and their full explanations on the fly, bypassing static databases entirely.
- **Technical Flashcards with Ace Editor:** Replaces standard text boxes with a professional, syntax-highlighted IDE (Ace Editor). Supports Python, JavaScript, Java, and C++.
- **Algorithmic AI Evaluation:** When code is submitted, the backend LLM (Groq Llama-3-70b) acts as a strict technical interviewer. It explicitly grades the code on **Time Complexity (Big-O)**, **Space Complexity**, and identifies **edge cases** the user may have missed.
- **Behavioral Mode (Voice & STAR Method):** Integrates WebRTC to allow users to verbally record their answers to behavioral questions (e.g., "Tell me about a time you failed").
- **Whisper API Transcription:** Audio is captured as `.webm` and sent to Groq's **Whisper-Large-V3** API for blazing-fast transcription.
- **STAR Scorecard:** The LLM strictly evaluates transcribed answers using the **STAR Method** (Situation, Task, Action, Result), returning a 1-10 score for each individual component and an overall critique.
- **Dynamic Follow-up Questioning:** If an answer is correct but lacks depth, the AI generates context-aware follow-up questions to simulate the pressure of a real human interviewer probing for details.
- **Historical Progress Radar:** All interview scores (Technical, Behavioral, System Design, etc.) are securely logged to MongoDB. The dashboard uses **Chart.js** to render an interactive Radar chart, allowing users to track their proficiency growth over time.

### 🔍 3. Semantic Search Engine & AI Rating System
A powerful fallback engine that indexes scraped course data using traditional machine learning and NLP.
- **TF-IDF Vectorization & Cosine Similarity:** Employs TF-IDF with bigram support for context-aware search, ranking courses based on true semantic relevance rather than just keyword matching.
- **AI-Powered Star Ratings:** Uses **NLTK VADER Sentiment Analysis** to score course descriptions and student reviews.
- **Review-Weighted Scoring:** When student reviews are available, ratings are heavily weighted (70%) based on the sentiment of real student feedback.
- **Platform Prestige Bonus:** Courses from elite institutions (MIT, Google, Stanford, IBM) receive an artificial prestige boost in the algorithm to guarantee high-quality results.
- **NLP Review Summarization:** Extracts up to 10 reviews per course from Coursera, tokenizes them, and performs frequency analysis to generate human-readable summaries (e.g., *"Based on 8 reviews, students frequently mention: algorithms, difficult, rewarding"*).

### 📊 4. Intelligence EDA (Exploratory Data Analysis) Dashboard
A dedicated visualization center for data-driven career decisions.
- **Market & Skill Visualization:** Features dynamic, interactive charts (powered by Chart.js/Plotly) that help users understand trending tech stacks, high-demand skills, and salary analytics.
- **Course Distribution Analytics:** Visualizes the spread of course difficulties, providers, and ratings across the scraped database.

### 🕷️ 5. Admin Dashboard & Multi-Platform Web Scraper
The backbone of the platform's data ingestion pipeline.
- **Secure Admin Portal:** A protected route allowing administrators to manage the underlying dataset.
- **CSV Data Uploads:** Admins can manually upload standard CSV files containing course data, which the backend safely parses and inserts into MongoDB.
- **Deep Web Scraping Engine:** Uses headless Chrome (Selenium) to scrape 24+ targets across 5 platforms (MIT OCW, Coursera, Cybrary, Khan Academy, CourseTalk).
- **Asynchronous Execution:** Scraping jobs run on background threads, preventing server lockups, while a real-time progress bar updates the UI dynamically.
- **robots.txt Compliant:** Respects crawling policies to ensure ethical data gathering.

---

## 🎨 Modern UI & UX Design
- **Glassmorphism Aesthetic:** Features translucent panels, soft glows, and blurred backdrops for a premium, native-app feel.
- **Fully Responsive & Accessible:** Fluid layouts adapt seamlessly to mobile, tablet, and desktop screens.
- **Dynamic Theming:** Smooth transitions between high-contrast Light Mode and deep Dark Mode.
- **Generative UI:** Micro-animations, loaders, and **Lucide Icons** respond instantly to AI streaming states.

---

## 🧪 How the AI Engine Works

### Structured JSON Enforcement & Prompt Engineering
To ensure the AI acts as a reliable software component rather than an unpredictable chatbot, all backend LLM prompts strictly enforce JSON formatting. By injecting rigid schemas into the system prompts (e.g., forcing keys for `"time_complexity"`, `"star_score"`, and `"followup"`), the Flask backend can safely parse and bind the AI's intelligence directly to UI components without relying on fragile regex hacks.

---

## 🔧 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | Python Flask, Threading (Async Processing) |
| **Frontend Languages** | HTML5, CSS3, Vanilla JavaScript |
| **Frontend Libraries** | Ace Editor (IDE), Chart.js (Radar/EDA), Lucide (Icons) |
| **Artificial Intelligence** | Groq API (Llama-3-70b-8192, Whisper-Large-V3), Google Gemini 2.5 Flash |
| **Natural Language Processing**| NLTK (VADER Sentiment, Tokenization, Stopwords) |
| **Machine Learning** | Scikit-Learn (TF-IDF + Cosine Similarity) |
| **Web Scraping** | Selenium (Headless Chrome) + BeautifulSoup4 |
| **Data Storage** | MongoDB (PyMongo), JSON, Pandas |

---

## 📝 License
This project is open-source and intended for educational purposes.

---

## 👤 Authors
**Marc Zaki, Muhammad Kandil, Retag Ahmed**
