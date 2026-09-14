import pandas as pd
from sqlalchemy import create_engine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

def get_recommendations(title, n=5):
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM movies', conn)
    
    df['combined'] = df['overview'].fillna('') + ' ' + df['genre_ids'].fillna('')
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(df['combined'])
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
    
    matches = df[df['title'] == title]
    if matches.empty:
        print(f"'{title}' not found in database.")
        return None
    
    idx = matches.index[0]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:n+1]
    return df.iloc[[i[0] for i in scores]]

if __name__ == "__main__":
    # Quick test - replace with an actual movie title from your database
    results = get_recommendations("Inception", n=5)
    if results is not None:
        print(results[['title', 'vote_average']])