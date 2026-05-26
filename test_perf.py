import time
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import pymongo, os
from dotenv import load_dotenv

load_dotenv()
db = pymongo.MongoClient(os.environ['MONGO_URI']).cs_recommender
collection = db.courses
t0 = time.time()
mongo_courses = list(collection.find({}, {'_id': 0}))
t1 = time.time()
df = pd.DataFrame(mongo_courses)
print(f"MongoDB load: {t1-t0:.2f}s")

t2 = time.time()
def build_search_profile(row):
    return f"{str(row.get('title',''))} {str(row.get('content_text',''))}".lower()
df['search_profile'] = df.apply(build_search_profile, axis=1)
t3 = time.time()
print(f"Build profile: {t3-t2:.2f}s")

t4 = time.time()
vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
vectorizer.fit_transform(df['search_profile'])
t5 = time.time()
print(f"TF-IDF: {t5-t4:.2f}s")
