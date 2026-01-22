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
    "hate", "kill", "stupid", "idiot", "dumb", "fool", "moron",
    "loser", "bitch", "crap", "ass", "damn", "suck", "shut up",
    "kill yourself", "die", "trash", "jerk", "ugly", "faggot", "slut", "whore",
    "retard", "dick", "piss", "hell", "bastard", "I", "You", "me","why","a","and"
]

# -------------------------
# DATABASE (permanent file)
# -------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), "mini_twitter.db")
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
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

c.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    type TEXT,
    from_user TEXT,
    tweet_id TEXT,
    ts REAL
)
""")

conn.commit()

# -------------------------
# HELPERS
# -------------------------
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_allowed(text):
    text = text.lower()
    return not any(word in text for word in BANNED_WORDS)

def get_username(uid):
    c.execute("SELECT username FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    return row[0] if row else "Unknown"

# -------------------------
# AUTH
# -------------------------
def register(email, username, password):
    uid = str(uuid4())
    try:
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (uid, email, username, hash_pw(password), time.time())
        )
        conn.commit()
        return "Account created."
    except sqlite3.IntegrityError:
        return "Username taken."

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
# FOLLOW SYSTEM
# -------------------------
def follow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if not row:
        return "User not found."
    tid = row[0]
    if uid == tid:
        return "Can't follow yourself."
    try:
        c.execute("INSERT INTO follows VALUES (?, ?)", (uid, tid))
        conn.commit()
        # Add notification
        nid = str(uuid4())
        c.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
            (nid, tid, "follow", get_username(uid), None, time.time())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return f"You now follow {target_username}"

def unfollow_user(uid, target_username):
    c.execute("SELECT id FROM users WHERE username=?", (target_username,))
    row = c.fetchone()
    if not row:
        return "User not found."
    tid = row[0]
    c.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (uid, tid))
    conn.commit()
    return f"Unfollowed {target_username}"

def get_following(uid):
    c.execute("SELECT following_id FROM follows WHERE follower_id=?", (uid,))
    return [row[0] for row in c.fetchall()]

# -------------------------
# TWEETS
# -------------------------
def create_tweet(uid, text):
    if not text:
        return "Tweet cannot be empty."
    if len(text) > 280:
        return "Tweet too long."
    if not is_allowed(text):
        return "Tweet blocked by moderation."

    tid = str(uuid4())
    c.execute(
        "INSERT INTO tweets VALUES (?, ?, ?, ?)",
        (tid, uid, text, time.time())
    )
    conn.commit()
    return "Tweet posted."

def like_tweet(uid, tid):
    try:
        c.execute("INSERT INTO likes VALUES (?, ?)", (tid, uid))
        conn.commit()
        # Add notification
        nid = str(uuid4())
        c.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
            (nid, get_tweet_author(tid), "like", get_username(uid), tid, time.time())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass

def get_tweet_author(tid):
    c.execute("SELECT author_id FROM tweets WHERE id=?", (tid,))
    row = c.fetchone()
    return row[0] if row else None

def home_feed(uid):
    following = get_following(uid) + [uid]
    placeholders = ",".join("?" * len(following))
    c.execute(f"""
        SELECT t.id, t.author_id, t.content, t.ts,
               (SELECT COUNT(*) FROM likes WHERE tweet_id=t.id)
        FROM tweets t
        WHERE t.author_id IN ({placeholders})
        ORDER BY t.ts DESC
    """, tuple(following))
    return c.fetchall()

# -------------------------
# NOTIFICATIONS
# -------------------------
def get_notifications(uid):
    c.execute("SELECT type, from_user, tweet_id, ts FROM notifications WHERE user_id=? ORDER BY ts DESC", (uid,))
    return c.fetchall()

# -------------------------
# STREAMLIT STATE
# -------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------------------------
# UI
# -------------------------
st.title(" Mini Twitter")

menu = ["Register", "Login", "Feed", "Post Tweet", "Follow/Unfollow", "Notifications", "Logout"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Register":
    email = st.text_input("Email")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        st.success(register(email, username, password))

elif choice == "Login":
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.success("Logged in!")
        else:
            st.error("Invalid login.")

elif choice == "Post Tweet":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        text = st.text_area("What's happening?")
        if st.button("Post"):
            st.success(create_tweet(st.session_state.user_id, text))

elif choice == "Feed":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        feed = home_feed(st.session_state.user_id)
        for tid, author_id, content, ts, likes in feed:
            st.write(f"**{get_username(author_id)}**: {content}")
            st.write(f"❤️ {likes}")
            if st.button(f"Like {tid}"):
                like_tweet(st.session_state.user_id, tid)
                st.experimental_rerun()

elif choice == "Follow/Unfollow":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        target = st.text_input("Username to follow/unfollow")
        col1, col2 = st.columns(2)
        if col1.button("Follow"):
            st.success(follow_user(st.session_state.user_id, target))
        if col2.button("Unfollow"):
            st.success(unfollow_user(st.session_state.user_id, target))

elif choice == "Notifications":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        notifs = get_notifications(st.session_state.user_id)
        for n_type, from_user, tweet_id, ts in notifs:
            msg = f"{from_user} "
            if n_type == "follow":
                msg += "followed you"
            elif n_type == "like":
                msg += f"liked your tweet {tweet_id}"
            st.write(msg)

elif choice == "Logout":
    logout()
    st.success("Logged out.")
