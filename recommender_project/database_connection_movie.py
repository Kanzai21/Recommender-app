import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Az14G",
        database="recommender_db"
    )
def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS movies (
        id INT PRIMARY KEY,
        title VARCHAR(255),
        overview TEXT,
        genre_ids VARCHAR(255),
        vote_average FLOAT,
        poster_path VARCHAR(255)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(255),
        movie_id INT,
        rating FLOAT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    print("Tables created successfully!")

if __name__ == "__main__":
    init_db()