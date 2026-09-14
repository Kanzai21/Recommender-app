import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from streamlit_lottie import st_lottie
import requests
import json

# ---------- CONFIG ----------
MEDIA_CONFIG = {
    'movies': {
        'table': 'movies',
        'title_col': 'title',
        'text_cols': ['overview', 'genre_names'],
        'score_col': 'vote_average',
        'image_col': 'poster_path',
        'image_prefix': 'https://image.tmdb.org/t/p/w200'
    },
    'anime': {
        'table': 'anime',
        'title_col': 'title',
        'text_cols': ['synopsis', 'genres'],
        'score_col': 'score',
        'image_col': 'image_url',
        'image_prefix': ''
    },
    'books': {
        'table': 'books',
        'title_col': 'title',
        'text_cols': ['subjects', 'author'],
        'score_col': 'first_publish_year',
        'image_col': 'cover_url',
        'image_prefix': ''
    }
}

SINGULAR_NAMES = {
    'movies': 'movie',
    'anime': 'anime',
    'books': 'book'
}

# ---------- DB CONNECTION ----------
def get_connection():
    return create_engine("mysql+pymysql://root:Az14G@localhost/recommender_db")

# ---------- DATA LOADING ----------
@st.cache_data(ttl=300)
def load_items(media_type):
    conn = get_connection()
    df = pd.read_sql(f'SELECT * FROM {MEDIA_CONFIG[media_type]["table"]}', conn)
    text_cols = MEDIA_CONFIG[media_type]['text_cols']

    if media_type == 'movies':
        df['combined'] = df['overview'].fillna('') + ' ' + (df['genre_names'].fillna('') + ' ') * 3
    else:
        df['combined'] = df[text_cols[0]].fillna('') + ' ' + df[text_cols[1]].fillna('')

    return df

def load_user_ratings(user_id, media_type):
    conn = get_connection()
    query = text("SELECT * FROM ratings WHERE user_id = :uid AND media_type = :mt")
    with conn.connect() as connection:
        result = connection.execute(query, {"uid": user_id, "mt": media_type})
        return pd.DataFrame(result.fetchall(), columns=result.keys())

def save_rating(user_id, item_id, media_type, rating):
    conn = get_connection()
    query = text('''
        INSERT INTO ratings (user_id, item_id, media_type, rating)
        VALUES (:uid, :iid, :mt, :r)
    ''')
    with conn.connect() as connection:
        connection.execute(query, {"uid": user_id, "iid": item_id, "mt": media_type, "r": rating})
        connection.commit()

# ---------- RECOMMENDATION LOGIC ----------
def get_personalized_recommendations(media_type, user_id, n=10):
    items_df = load_items(media_type)
    ratings_df = load_user_ratings(user_id, media_type)
    config = MEDIA_CONFIG[media_type]

    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(items_df['combined'])

    if len(ratings_df) == 0:
        return items_df.sort_values(config['score_col'], ascending=False).head(n), "popular"

    rated_ids = ratings_df['item_id'].tolist()
    id_to_index = {v: i for i, v in enumerate(items_df['id'])}
    valid_pairs = [(id_to_index[rid], r) for rid, r in zip(ratings_df['item_id'], ratings_df['rating']) if rid in id_to_index]

    if not valid_pairs:
        return items_df.sort_values(config['score_col'], ascending=False).head(n), "popular"

    indices, weights = zip(*valid_pairs)
    weights = np.array(weights).reshape(-1, 1)
    rated_vectors = tfidf_matrix[list(indices)]

    user_profile = np.asarray(rated_vectors.multiply(weights).sum(axis=0) / weights.sum())

    sims = cosine_similarity(user_profile, tfidf_matrix).flatten()
    items_df = items_df.copy()
    items_df['similarity'] = sims

    unrated = items_df[~items_df['id'].isin(rated_ids)]
    return unrated.sort_values('similarity', ascending=False).head(n), "personalized"

def get_similar_items(media_type, title, n=10):
    items_df = load_items(media_type)
    config = MEDIA_CONFIG[media_type]

    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(items_df['combined'])
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

    matches = items_df[items_df[config['title_col']] == title]
    if matches.empty:
        return None

    idx = matches.index[0]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:n+1]
    result = items_df.iloc[[i[0] for i in scores]].copy()
    result['similarity'] = [s[1] for s in scores]
    return result

def get_similar_items_by_genre(media_type, title, n=10, require_all_genres=True):
    items_df = load_items(media_type)
    config = MEDIA_CONFIG[media_type]
    genre_col = 'genre_names' if media_type == 'movies' else config['text_cols'][1]

    matches = items_df[items_df[config['title_col']] == title]
    if matches.empty:
        return None

    source_row = matches.iloc[0]
    source_genres = set(str(source_row[genre_col]).split())

    if not source_genres or source_genres == {''}:
        return get_similar_items(media_type, title, n)

    def genre_match(row_genres):
        row_genre_set = set(str(row_genres).split())
        if require_all_genres:
            return source_genres.issubset(row_genre_set)
        else:
            return len(source_genres & row_genre_set) > 0

    candidates = items_df[items_df[genre_col].apply(genre_match)].copy()
    candidates = candidates[candidates[config['title_col']] != title]

    if candidates.empty:
        return None

    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    all_text = pd.concat([matches['combined'], candidates['combined']])
    tfidf_matrix = tfidf.fit_transform(all_text)

    source_vec = tfidf_matrix[0]
    candidate_vecs = tfidf_matrix[1:]
    sims = cosine_similarity(source_vec, candidate_vecs).flatten()

    candidates['similarity'] = sims
    return candidates.sort_values('similarity', ascending=False).head(n)

# ---------- LOTTIE HELPER ----------
def load_lottie_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Lottie file not found at: {filepath}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Lottie file found but invalid JSON: {e}")
        return None

lottie_anim = load_lottie_file(r"C:\recommender_project\eso Animate rio.json")

# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="My Recommender", layout="wide")

col_title, col_anim = st.columns([4, 1])
with col_title:
    st.title("🎬📚🎌 Personal Recommender")
with col_anim:
    if lottie_anim:
        st_lottie(lottie_anim, height=120, key="header_anim")

user_id = st.text_input("Your name/ID", value="guest")

tab1, tab2, tab3 = st.tabs(["🎬 Movies", "🎌 Anime", "📚 Books"])

# ---------- SEARCH SECTION ----------
def render_search_section(media_type):
    config = MEDIA_CONFIG[media_type]
    items_df = load_items(media_type)

    st.subheader(f"🔍 Search {media_type}")
    search_query = st.text_input(
        "Search by title:",
        key=f"search_input_{media_type}",
        placeholder=f"Type a {SINGULAR_NAMES[media_type]} title..."
    )

    if search_query:
        mask = items_df[config['title_col']].str.contains(search_query, case=False, na=False)
        results = items_df[mask].head(20)

        if results.empty:
            st.info("No matches found.")
        else:
            st.caption(f"Found {len(results)} result(s):")
            cols = st.columns(5)
            for i, (_, row) in enumerate(results.iterrows()):
                with cols[i % 5]:
                    with st.container(border=True):
                        img = row.get(config['image_col'])
                        if img:
                            img_url = config['image_prefix'] + img if config['image_prefix'] else img
                            st.image(img_url, use_container_width=True)
                        title_display = row[config['title_col']]
                        if len(str(title_display)) > 40:
                            title_display = str(title_display)[:40] + "..."
                        st.caption(f"**{title_display}**")
                        st.caption(f"⭐ {row.get(config['score_col'], 'N/A')}")

                        with st.expander("Details"):
                            detail_text_col = config['text_cols'][0]
                            detail_text = row.get(detail_text_col, '')
                            if detail_text:
                                st.write(str(detail_text)[:500] + ("..." if len(str(detail_text)) > 500 else ""))

# ---------- MAIN MEDIA TAB ----------
def render_media_tab(media_type, tab):
    config = MEDIA_CONFIG[media_type]
    with tab:
        sub_tab1, sub_tab2 = st.tabs(["📊 Recommendations", "🔍 Search"])

        with sub_tab1:
            n_ratings = len(load_user_ratings(user_id, media_type))
            st.caption(f"You've rated {n_ratings} {media_type} so far. More ratings = better recommendations.")

            recs, mode = get_personalized_recommendations(media_type, user_id, n=10)
            if mode == "popular":
                st.info("Showing popular picks — rate a few items below to get personalized recommendations.")
            else:
                st.success("Personalized picks based on your ratings.")

            cols = st.columns(5)
            for i, (_, row) in enumerate(recs.iterrows()):
                with cols[i % 5]:
                    with st.container(border=True):
                        img = row.get(config['image_col'])
                        if img:
                            img_url = config['image_prefix'] + img if config['image_prefix'] else img
                            st.image(img_url, use_container_width=True)
                        title_display = row[config['title_col']]
                        if len(str(title_display)) > 40:
                            title_display = str(title_display)[:40] + "..."
                        st.caption(f"**{title_display}**")
                        st.caption(f"⭐ {row.get(config['score_col'], 'N/A')}")

            st.divider()

            st.subheader(f"🎯 Find {media_type} similar to one you like")
            items_df = load_items(media_type)
            search_title = st.selectbox(
                "Enjoyed this one? Find similar:",
                items_df[config['title_col']].dropna().unique(),
                key=f"similar_search_{media_type}"
            )
            if st.button("Find similar", key=f"find_similar_{media_type}"):
                similar = get_similar_items_by_genre(media_type, search_title, n=10, require_all_genres=True)
                if similar is None or similar.empty:
                    st.warning("No exact genre matches found — showing loosely related titles instead.")
                    similar = get_similar_items_by_genre(media_type, search_title, n=10, require_all_genres=False)

                if similar is not None and not similar.empty:
                    st.markdown(f"**Because you liked '{search_title}':**")
                    sim_cols = st.columns(5)
                    for i, (_, row) in enumerate(similar.iterrows()):
                        with sim_cols[i % 5]:
                            with st.container(border=True):
                                img = row.get(config['image_col'])
                                if img:
                                    img_url = config['image_prefix'] + img if config['image_prefix'] else img
                                    st.image(img_url, use_container_width=True)
                                title_display = row[config['title_col']]
                                if len(str(title_display)) > 40:
                                    title_display = str(title_display)[:40] + "..."
                                st.caption(f"**{title_display}**")
                                st.caption(f"Similarity: {row['similarity']:.2f}")
                else:
                    st.warning("Couldn't find similar titles.")

            st.divider()

            st.subheader(f"⭐ Rate a {SINGULAR_NAMES[media_type]}")
            chosen_title = st.selectbox("Pick one:", items_df[config['title_col']].dropna().unique(), key=f"select_{media_type}")
            rating = st.slider("Your rating", 1, 5, 3, key=f"rating_{media_type}")
            if st.button("Submit rating", key=f"submit_{media_type}"):
                item_id = items_df[items_df[config['title_col']] == chosen_title]['id'].values[0]
                save_rating(user_id, item_id, media_type, rating)
                st.cache_data.clear()
                st.success("Rating saved! Refresh recommendations above.")
                st.rerun()

        with sub_tab2:
            render_search_section(media_type)

render_media_tab('movies', tab1)
render_media_tab('anime', tab2)
render_media_tab('books', tab3)