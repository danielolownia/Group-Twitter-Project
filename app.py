import streamlit as st
import sqlite3
import time
import hashlib
from uuid import uuid4
import os

# -------------------------
# CONFIG
# -------------------------
BANNED_WORDS = [
    "hate", "kill", "stupid", "idiot", "dumb", "moron", "loser",
    "bitch", "slut", "whore", "retard", "faggot",
    "kill yourself", "die", "trash", "jerk", "ugly",
    "asshole", "bastard", "piss", "dick"
]

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
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_allowed(text):
    return not any(word in text.lower() for word in BANNED_WORDS)

def get_username(uid):
    c.execute("SELECT username FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    return row[0] if row else "Unknown"

def follower_count(uid):
    c.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (uid,))
    return c.fetchone()[0]

# 🔹 NEW: check if user already liked a tweet
def has_liked(uid, tid):
    c.execute(
        "SELECT 1 FROM likes WHERE tweet_id=? AND user_id=?",
        (tid, uid)
    )
    return c.fetchone() is not None

# -------------------------
# AUTH
# -------------------------
def register(email, username, password):
    if not username or not password:
        return "Username and password required."

    try:
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), email, username, hash_pw(password), time.time())
        )
        conn.commit()
        return "Account created. Log in now."
    except sqlite3.IntegrityError:
        return "Username already taken."

def login(username, password):
    c.execute(
        "SELECT id FROM users WHERE username=? AND password=?",
        (username, hash_pw(password))
    )
    row = c.fetchone()
    if row:
        st.session_state.user_id = row[0]
        return True
    return False

def logout():
    st.session_state.user_id = None

# -------------------------
# FOLLOW
# -------------------------
def follow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if not row or row[0] == uid:
        return "Invalid user."

    try:
        c.execute("INSERT INTO follows VALUES (?, ?)", (uid, row[0]))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    return f"You followed {target_username}"

def unfollow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if row:
        c.execute(
            "DELETE FROM follows WHERE follower_id=? AND following_id=?",
            (uid, row[0])
        )
        conn.commit()
    return "Unfollowed"

# -------------------------
# TWEETS
# -------------------------
def create_tweet(uid, text, image_url):
    if not text:
        return "Tweet cannot be empty."
    if len(text) > 280:
        return "Tweet too long."
    if not is_allowed(text):
        return "Tweet blocked."

    c.execute("""
        SELECT content FROM tweets
        WHERE author_id=?
        ORDER BY ts DESC
        LIMIT 1
    """, (uid,))
    last = c.fetchone()
    if last and last[0] == text:
        return "You just posted this."

    c.execute(
        "INSERT INTO tweets VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), uid, text, image_url, time.time())
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

# 🔹 NEW: unlike tweet
def unlike_tweet(uid, tid):
    c.execute(
        "DELETE FROM likes WHERE tweet_id=? AND user_id=?",
        (tid, uid)
    )
    conn.commit()

# -------------------------
# FEED
# -------------------------
def home_feed():
    c.execute("""
        SELECT
            t.id,
            t.author_id,
            t.content,
            t.image_url,
            (SELECT COUNT(*) FROM likes WHERE tweet_id=t.id)
        FROM tweets t
        ORDER BY t.ts DESC
    """)
    return c.fetchall()

# -------------------------
# SESSION
# -------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "tweet_text" not in st.session_state:
    st.session_state.tweet_text = ""

# -------------------------
# UI
# -------------------------
st.title("🐦 Mini Twitter")

menu = ["Register", "Login", "Feed", "Post Tweet", "Follow / Unfollow", "Logout"]
choice = st.sidebar.selectbox("Menu", menu)

# REGISTER
if choice == "Register":
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
        if login(username, password):
            st.success("Logged in!")
        else:
            st.error("Invalid login.")

# POST
elif choice == "Post Tweet":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        st.session_state.tweet_text = st.text_area(
            "What's happening?",
            value=st.session_state.tweet_text
        )
        image_url = st.text_input("Image URL (optional)")

        if st.button("Post"):
            msg = create_tweet(
                st.session_state.user_id,
                st.session_state.tweet_text,
                image_url
            )
            st.success(msg)
            if msg == "Tweet posted.":
                st.session_state.tweet_text = ""
                st.rerun()

# FEED
elif choice == "Feed":
    for tid, author, content, img, likes in home_feed():
        st.write(f"**{get_username(author)}** · {follower_count(author)} followers")
        st.write(content)
        st.write(f"❤️ {likes} likes")

        if img:
            st.image(img)

        col1, col2 = st.columns(2)
        if st.session_state.user_id:
            liked = has_liked(st.session_state.user_id, tid)

            if col1.button(
                "💔 Unlike" if liked else "👍 Like",
                key=f"like-{tid}"
            ):
                if liked:
                    unlike_tweet(st.session_state.user_id, tid)
                else:
                    like_tweet(st.session_state.user_id, tid)
                st.rerun()

            if author == st.session_state.user_id:
                if col2.button("Delete", key=f"del-{tid}"):
                    delete_tweet(author, tid)
                    st.rerun()

        st.divider()

# FOLLOW
elif choice == "Follow / Unfollow":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        target = st.text_input("Username")
        col1, col2 = st.columns(2)
        if col1.button("Follow"):
            st.success(follow_user(st.session_state.user_id, target))
        if col2.button("Unfollow"):
            st.success(unfollow_user(st.session_state.user_id, target))

# LOGOUT
elif choice == "Logout":
    logout()
    st.success("Logged out.")
