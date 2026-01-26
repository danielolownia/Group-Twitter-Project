import streamlit as st
import sqlite3
import time
import hashlib
from uuid import uuid4
import os

# -------------------------
# GLOBAL STYLES
# -------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Chivo+Mono:wght@700&family=Inter:wght@400;600&display=swap');

    header {visibility: hidden;}
    .stAppViewMain > div:nth-child(1) {padding-top: 0rem;}
    [data-testid="stDecoration"] {display: none;}

    .stApp {
        background-color: #64B5F6;
        background-image: radial-gradient(#ffffff33 1px, transparent 1px);
        background-size: 20px 20px;
        font-family: 'Inter', sans-serif;
        color: white;
    }

    .main-title {
        font-family: 'Courier', monospace;
        font-size: 4rem;
        text-align: center;
        color: white;
        padding: 20px 0;
        letter-spacing: -2px;
        text-shadow: 3px 3px 0px #1565C0;
    }

    .stMarkdown, p, span, label, .stSubheader {
        color: white !important;
        font-family: 'Courier', monospace;
    }

    div.stButton > button {
        width: 100%;
        background-color: #1565C0 !important;
        color: white !important;
        border: 2px solid #0D47A1 !important;
        font-weight: bold;
        border-radius: 12px;
        transition: 0.2s ease-in-out;
    }

    div.stButton > button:hover {
        background-color: #0D47A1 !important;
        border-color: white !important;
        transform: scale(1.02);
    }

    div.stButton > button[key^="like-"] {
        width: 48px !important;
        height: 48px !important;
        border-radius: 50% !important;
        padding: 0 !important;
        font-size: 20px !important;
    }

    .stTextInput input, .stTextArea textarea, .stSelectbox div {
        background-color: rgba(255,255,255,0.9) !important;
        color: #0D47A1 !important;
        border-radius: 10px !important;
    }

    [data-testid="stVerticalBlock"] > div {
        background: rgba(255,255,255,0.08);
        border-radius: 15px;
        padding: 12px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------
# CONFIG
# -------------------------
BANNED_WORDS = ["hate", "kill", "stupid"]

# -------------------------
# DATABASE
# -------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), "mini_twitter.db")
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# -------------------------
# TABLES
# -------------------------
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT,
    username TEXT UNIQUE,
    password TEXT,
    created REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    author_id TEXT,
    content TEXT,
    image_url TEXT,
    ts REAL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS likes (
    tweet_id TEXT,
    user_id TEXT,
    PRIMARY KEY (tweet_id, user_id)
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS follows (
    follower_id TEXT,
    following_id TEXT,
    PRIMARY KEY (follower_id, following_id)
)
""")

conn.commit()

# -------------------------
# HELPERS
# -------------------------
def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def get_username(uid):
    c.execute("SELECT username FROM users WHERE id=?", (uid,))
    r = c.fetchone()
    return r[0] if r else "Unknown"

def follower_count(uid):
    c.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (uid,))
    return c.fetchone()[0]

def has_liked(uid, tid):
    c.execute("SELECT 1 FROM likes WHERE tweet_id=? AND user_id=?", (tid, uid))
    return c.fetchone() is not None

# -------------------------
# FOLLOW HELPERS (NEW)
# -------------------------
def follow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if not row or row[0] == uid:
        return "Invalid user."

    try:
        c.execute("INSERT INTO follows VALUES (?, ?)", (uid, row[0]))
        conn.commit()
        return f"You followed @{target_username}"
    except sqlite3.IntegrityError:
        return "Already following."

def unfollow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if row:
        c.execute(
            "DELETE FROM follows WHERE follower_id=? AND following_id=?",
            (uid, row[0])
        )
        conn.commit()
        return f"You unfollowed @{target_username}"
    return "User not found."

# -------------------------
# AUTH
# -------------------------
def register(email, username, password):
    try:
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), email, username, hash_pw(password), time.time())
        )
        conn.commit()
        return "Account created."
    except sqlite3.IntegrityError:
        return "Username already taken."

def login(username, password):
    c.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (username, hash_pw(password))
    )
    r = c.fetchone()
    if r:
        st.session_state.user_id = r[0]
        return True
    return False

def logout():
    st.session_state.user_id = None

# -------------------------
# TWEETS
# -------------------------
def create_tweet(uid, text, img):
    if not text:
        return "Tweet empty."
    c.execute(
        "INSERT INTO tweets VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), uid, text, img, time.time())
    )
    conn.commit()
    return "Tweet posted."

def delete_tweet(uid, tid):
    c.execute("DELETE FROM tweets WHERE id=? AND author_id=?", (tid, uid))
    conn.commit()

def like_tweet(uid, tid):
    try:
        c.execute("INSERT INTO likes VALUES (?, ?)", (tid, uid))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

def unlike_tweet(uid, tid):
    c.execute("DELETE FROM likes WHERE tweet_id=? AND user_id=?", (tid, uid))
    conn.commit()

# -------------------------
# FEED
# -------------------------
def home_feed():
    c.execute("""
        SELECT t.id, t.author_id, t.content, t.image_url,
        (SELECT COUNT(*) FROM likes WHERE tweet_id=t.id)
        FROM tweets t ORDER BY t.ts DESC
    """)
    return c.fetchall()

# -------------------------
# SESSION
# -------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------------------------
# UI
# -------------------------
st.markdown('<h1 class="main-title">Mini Twitter</h1>', unsafe_allow_html=True)

menu = ["Register", "Login", "Feed", "Post Tweet", "Follow / Unfollow", "Logout"]
choice = st.sidebar.selectbox("Menu", menu)

# FOLLOW UI (NEW)
if choice == "Follow / Unfollow":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        target = st.text_input("Username to follow/unfollow")
        col1, col2 = st.columns(2)
        if col1.button("Follow"):
            st.success(follow_user(st.session_state.user_id, target))
        if col2.button("Unfollow"):
            st.success(unfollow_user(st.session_state.user_id, target))

# REGISTER
elif choice == "Register":
    email = st.text_input("Email")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        st.success(register(email, username, password))

# LOGIN
elif choice == "Login":
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        st.success("Logged in!") if login(username, password) else st.error("Invalid login")

# POST
elif choice == "Post Tweet":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        text = st.text_area("What's happening?")
        img = st.text_input("Image URL (optional)")
        if st.button("Post"):
            st.success(create_tweet(st.session_state.user_id, text, img))
            st.rerun()

# FEED
elif choice == "Feed":
    for tid, author, content, img, likes in home_feed():
        st.write(f"**@{get_username(author)}** · {follower_count(author)} followers")
        st.write(content)
        st.write(f"❤️ {likes} likes")

        col1, col2 = st.columns([1, 8])
        if st.session_state.user_id:
            liked = has_liked(st.session_state.user_id, tid)
            if col1.button("❤️" if liked else "♡", key=f"like-{tid}"):
                unlike_tweet(st.session_state.user_id, tid) if liked else like_tweet(st.session_state.user_id, tid)
                st.rerun()

            if author == st.session_state.user_id:
                if col2.button("Delete", key=f"del-{tid}"):
                    delete_tweet(author, tid)
                    st.rerun()

        if img:
            st.image(img)
        st.divider()

# LOGOUT
elif choice == "Logout":
    logout()
    st.success("Logged out.")
