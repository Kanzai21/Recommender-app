import requests
import time
from sqlalchemy import create_engine, text
import pandas as pd

def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

def fetch_books_by_subject(subject, limit=100, retries=3):
    url = f"https://openlibrary.org/subjects/{subject}.json?limit={limit}"
    
    for attempt in range(retries):
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            return res.json().get('works', [])
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(3)
            else:
                print(f"  Giving up on '{subject}' after {retries} attempts.")
                return []
    return []

def store_books(books):
    if not books:
        return
    conn = get_connection()
    
    records = []
    for b in books:
        title = b.get('title', '')[:250]
        authors = ', '.join([a['name'] for a in b.get('authors', [])])[:250]
        subjects = ' '.join(b.get('subject', [])[:10])[:490]
        cover_id = b.get('cover_id')
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
        
        records.append({
            'id': b['key'].split('/')[-1],
            'title': title,
            'author': authors,
            'description': '',
            'subjects': subjects,
            'first_publish_year': b.get('first_publish_year'),
            'cover_url': cover_url
        })
    
    df = pd.DataFrame(records).drop_duplicates(subset='id')
    
    with conn.connect() as connection:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            # Force any NaN to None, no matter what
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
            
            query = text('''
                INSERT INTO books (id, title, author, description, subjects, first_publish_year, cover_url)
                VALUES (:id, :title, :author, :description, :subjects, :first_publish_year, :cover_url)
                ON DUPLICATE KEY UPDATE title=VALUES(title)
            ''')
            connection.execute(query, row_dict)
        connection.commit()

if __name__ == "__main__":
    subjects = [
        "fiction", "fantasy", "science_fiction", "mystery", "romance",
        "horror", "thriller", "adventure", "historical_fiction",
        "literary_fiction", "crime", "drama",
        "biography", "history", "self_help", "psychology", "philosophy",
        "science", "religion", "politics", "economics", "true_crime",
        "business", "health", "travel", "cooking",
        "young_adult", "children", "poetry", "comics", "graphic_novels",
        "classic_literature", "short_stories", "essays", "art",
        "music", "sports", "nature", "technology"
    ]
    
    total = 0
    for subj in subjects:
        print(f"Fetching subject: {subj}...")
        books = fetch_books_by_subject(subj, limit=500)
        store_books(books)
        total += len(books)
        print(f"  Stored {len(books)} books from '{subj}'")
        time.sleep(1)
    
    print(f"\nTotal fetched: {total} (duplicates auto-merged)")