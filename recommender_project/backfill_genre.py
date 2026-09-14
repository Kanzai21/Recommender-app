import requests
import time
from sqlalchemy import create_engine, text
import pandas as pd

API_KEY = "your_tmdb_api_key_here"

def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

def fetch_movie_keywords(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/keywords?api_key={API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        return ' '.join([k['name'] for k in res.get('keywords', [])])
    except requests.exceptions.RequestException:
        return ''

def backfill_keywords():
    conn = get_connection()
    df = pd.read_sql('SELECT id FROM movies', conn)
    
    with conn.connect() as connection:
        for i, row in df.iterrows():
            keywords = fetch_movie_keywords(row['id'])
            connection.execute(
                text('UPDATE movies SET keywords = :kw WHERE id = :id'),
                {'kw': keywords, 'id': row['id']}
            )
            if i % 100 == 0:
                connection.commit()
                print(f"Processed {i}/{len(df)} movies...")
            time.sleep(0.05)  # stay safely within rate limits
    
    print("Keyword backfill complete!")

if __name__ == "__main__":
    backfill_keywords()