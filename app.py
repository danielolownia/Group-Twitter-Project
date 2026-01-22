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
    "hate", "kill", "stupid", "idiot", "moron", "loser",
    "bitch", "slut", "whore", "retard", "faggot",
    "kill yourself", "die", "trash", "jerk", "ugly",
    "asshole", "bastard"
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
def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def is_allowed(text):
    return not any(w in text.lower() for w in BANNED_WORDS)

def get_username(uid):
    c.execute("SELECT username FROM users WHERE id=?", (uid,))
    r = c.fetchone()
    return r[0] if r else "Unknown"

def follower_count(uid):
    c.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (uid,))
    return c.fetchone()[0]

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
        return "Account created"
    except sqlite3.IntegrityError:
        return "Username already exists"

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
# FOLLOW
# -------------------------
def follow_user(uid, target):
    c.execute("SELECT id FROM users WHERE username=?", (target,))
    r = c.fetchone()
    if not r:
        return "User not found"
    tid = r[0]
    if uid == tid:
        return "Can't follow yourself"
    try:
        c.execute("INSERT INTO follows VALUES (?, ?)", (uid, tid))
        conn.commit()
        c.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid4()), tid, "follow", get_username(uid), None, time.time())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return f"Following {target}"

def unfollow_user(uid, target):
    c.execute("SELECT id FROM users WHERE username=?", (target,))
    r = c.fetchone()
    if r:
        c.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (uid, r[0]))
        conn.commit()
        return f"Unfollowed {target}"
    return "User not found"

# -------------------------
# TWEETS
# -------------------------
def create_tweet(uid, text, image_url):
    if not text:
        return "Tweet cannot be empty"
    if len(text) > 280:
        return "Tweet too long"
    if not is_allowed(text):
        return "Tweet blocked"

    # Prevent duplicate posts
    c.execute(
        "SELECT 1 FROM tweets WHERE author_id=? AND content=?",
        (uid, text)
    )
    if c.fetchone():
        return "You already posted this"

    c.execute(
        "INSERT INTO tweets VALUES (?, ?, ?, ?, ?)",
        (str(uuid4()), uid, text, image_url, time.time())
    )
    conn.commit()
    return "Tweet posted"

def delete_tweet(uid, tid):
    c.execute("DELETE FROM tweets WHERE id=? AND author_id=?", (tid, uid))
    conn.commit()

def like_tweet(uid, tid):
    try:
        c.execute("INSERT INTO likes VALUES (?, ?)", (tid, uid))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

# -------------------------
# FEED
# -------------------------
def home_feed():
    c.execute("""
        SELECT t.id, t.author_id, t.content, t.image_url, t.ts,
               (SELECT COUNT(*) FROM likes WHERE tweet_id=t.id)
        FROM tweets t
        ORDER BY t.ts DESC
    """)
    return c.fetchall()

# -------------------------
# SEARCH
# -------------------------
def search_users(query):
    c.execute("SELECT username FROM users WHERE username LIKE ?", (f"%{query}%",))
    return [r[0] for r in c.fetchall()]

# -------------------------
# NOTIFICATIONS
# -------------------------
def get_notifications(uid):
    c.execute(
        "SELECT type, from_user FROM notifications WHERE user_id=? ORDER BY ts DESC",
        (uid,)
    )
    return c.fetchall()

# -------------------------
# STREAMLIT STATE
# -------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------------------------
# UI
# -------------------------
st.title("🐦 Mini Twitter")

menu = ["Register", "Login", "Feed", "Post", "Search Users", "Follow", "Notifications", "Logout"]
choice = st.sidebar.selectbox("Menu", menu)

# REGISTER
if choice == "Register":
    st.success(register(
        st.text_input("Email"),
        st.text_input("Username"),
        st.text_input("Password", type="password")
    )) if st.button("Register") else None

# LOGIN
elif choice == "Login":
    if st.button("Login"):
        if login(st.text_input("Username"), st.text_input("Password", type="password")):
            st.success("Logged in")
        else:
            st.error("Invalid login")

# POST
elif choice == "Post":
    if not st.session_state.user_id:
        st.warning("Login first")
    else:
        text = st.text_area("What's happening?")
        image_url = st.text_input("Image URL (optional)")
        if st.button("Post"):
            st.success(create_tweet(st.session_state.user_id, text, image_url))
            st.rerun()

# FEED
elif choice == "Feed":
    for tid, uid, content, img, ts, likes in home_feed():
        st.write(f"**{get_username(uid)}** · {follower_count(uid)} followers")
        st.write(content)
        if img:
            st.image(img)
        st.write(f"❤️ {likes}")

        col1, col2 = st.columns(2)
        if st.session_state.user_id:
            if col1.button("Like", key=f"like-{tid}"):
                like_tweet(st.session_state.user_id, tid)
                st.rerun()
            if uid == st.session_state.user_id:
                if col2.button("Delete", key=f"del-{tid}"):
                    delete_tweet(st.session_state.user_id, tid)
                    st.rerun()
        st.divider()

# SEARCH USERS
elif choice == "Search Users":
    q = st.text_input("Search username")
    for u in search_users(q):
        st.write(u)

# FOLLOW
elif choice == "Follow":
    target = st.text_input("Username")
    if st.button("Follow"):
        st.success(follow_user(st.session_state.user_id, target))
    if st.button("Unfollow"):
        st.success(unfollow_user(st.session_state.user_id, target))

# NOTIFICATIONS
elif choice == "Notifications":
    for t, f in get_notifications(st.session_state.user_id):
        st.write(f"{f} {t}ed you")

# LOGOUT
elif choice == "Logout":
    logout()
    st.success("Logged out")
