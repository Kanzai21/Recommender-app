import kagglehub
import os
import pandas as pd
from sqlalchemy import create_engine, text

def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

def load_kaggle_anime():
    path = kagglehub.dataset_download("svanoo/myanimelist-dataset")
    
    df = pd.read_csv(
        os.path.join(path, "anime.csv"),
        sep='\t',
        engine='python',
        on_bad_lines='skip'
    )
    
    print(f"Loaded {len(df)} rows from CSV")
    
    records = []
    for _, row in df.iterrows():
        title = str(row.get('title', ''))[:250]
        synopsis = str(row.get('synopsis', '') or '')[:5000]
        genres = str(row.get('genres', '') or '')[:250]
        score = row.get('score', 0)
        image_url = row.get('main_pic', None)
        
        records.append({
            'id': row['anime_id'],
            'title': title,
            'synopsis': synopsis,
            'genres': genres,
            'score': score,
            'image_url': image_url
        })
    
    result_df = pd.DataFrame(records).drop_duplicates(subset='id')
    result_df = result_df.where(pd.notnull(result_df), None)
    
    conn = get_connection()
    with conn.connect() as connection:
        for i, row in result_df.iterrows():
            row_dict = row.to_dict()
            row_dict = {k: (None if pd.isna(v) else v) for k, v in row_dict.items()}
            
            query = text('''
                INSERT INTO anime (id, title, synopsis, genres, score, image_url)
                VALUES (:id, :title, :synopsis, :genres, :score, :image_url)
                ON DUPLICATE KEY UPDATE title=VALUES(title)
            ''')
            connection.execute(query, row_dict)
            
            if i % 1000 == 0:
                connection.commit()
                print(f"  Inserted {i}/{len(result_df)}...")
        
        connection.commit()
    
    print(f"Done! Loaded {len(result_df)} anime into database.")

if __name__ == "__main__":
    load_kaggle_anime()