from pydoc import text
import time
import requests
from sqlalchemy import create_engine, text

from backfill_genre import fetch_genre_map

API_KEY = "cb9dfe393b337b91bbe63e235d8b47d2"  # replace with your actual key

def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

def fetch_movies_bulk(start_page=1, end_page=500, endpoint="popular"):
    all_movies = []
    for page in range(start_page, end_page + 1):
        url = f"https://api.themoviedb.org/3/movie/{endpoint}?api_key={API_KEY}&page={page}"
        res = requests.get(url).json()
        
        if 'results' not in res:
            print(f"Stopped at page {page}: {res.get('status_message', 'Unknown error')}")
            break
        
        all_movies.extend(res['results'])
        
        if page % 20 == 0:
            print(f"Fetched {page} pages, {len(all_movies)} movies so far...")
        
        time.sleep(0.05)  # small delay to stay well within rate limits
    
    return all_movies

def fetch_popular_movies(pages=1):
    movies = []
    for page in range(1, pages + 1):
        url = f"https://api.themoviedb.org/3/movie/popular?api_key={API_KEY}&page={page}"
        res = requests.get(url).json()
        movies.extend(res['results'])
    return movies

def store_movies(movies, genre_map):
    conn = get_connection()
    with conn.connect() as connection:
        for m in movies:
            genre_names = ' '.join([genre_map.get(gid, '') for gid in m.get('genre_ids', [])])
            query = text('''
                INSERT INTO movies (id, title, overview, genre_ids, genre_names, vote_average, poster_path)
                VALUES (:id, :title, :overview, :genre_ids, :genre_names, :vote_average, :poster_path)
                ON DUPLICATE KEY UPDATE title=VALUES(title)
            ''')
            connection.execute(query, {
                'id': m['id'], 'title': m['title'], 'overview': m['overview'],
                'genre_ids': str(m['genre_ids']), 'genre_names': genre_names,
                'vote_average': m['vote_average'], 'poster_path': m.get('poster_path')
            })
        connection.commit()
    connection.close()

if __name__ == "__main__":
    genre_map = fetch_genre_map()
    movies = fetch_popular_movies(pages=1)
    movies2 = fetch_movies_bulk(start_page = 1,end_page = 500, endpoint = "top_rated")
    store_movies(movies, genre_map)
    store_movies(movies2, genre_map)
    print(f"Stored {len(movies)} popular movies successfully!")
    print(f"Stored {len(movies2)} top-rated movies successfully!")