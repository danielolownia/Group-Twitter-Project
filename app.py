import streamlit as st
import time
import hashlib
from uuid import uuid4

# -------------------------
# CONFIG
# -------------------------
BANNED_WORDS = ["hate", "kill", "stupid", "Hell", "fuck", "idiot", "dunce", "Daniel"]

# -------------------------
# IN-MEMORY DATABASE
# -------------------------
users = {}
followers = {}
following = {}
notifications = {}
tweets_db = {}

# -------------------------
# HELPERS
# -------------------------
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_allowed(content):
    content = content.lower()
    return not any(word in content for word in BANNED_WORDS)

# -------------------------
# AUTH
# -------------------------
def register(email, username, password):
    for u in users.values():
        if u["username"] == username:
            return None

    uid = str(uuid4())
    users[uid] = {
        "id": uid,
        "email": email,
        "username": username,
        "password": hash_pw(password),
        "created": time.time()
    }

    followers[uid] = set()
    following[uid] = set()
    notifications[uid] = []
    return uid

def login(username, password):
    for uid, user in users.items():
        if user["username"] == username and user["password"] == hash_pw(password):
            return uid
    return None

# -------------------------
# TWEETS
# -------------------------
class Tweet:
    def __init__(self, author_id, content):
        if not is_allowed(content):
            raise ValueError("Blocked by moderation")

        self.id = str(uuid4())
        self.author_id = author_id
        self.content = content
        self.likes = set()
        self.ts = time.time()

def create_tweet(user_id, text):
    if not text or len(text) > 280:
        return

    tweet = Tweet(user_id, text)
    tweets_db[tweet.id] = tweet

def like_tweet(user_id, tweet_id):
    tweets_db[tweet_id].likes.add(user_id)

def home_feed(user_id):
    feed_users = following[user_id] | {user_id}
    return sorted(
        [t for t in tweets_db.values() if t.author_id in feed_users],
        key=lambda t: t.ts,
        reverse=True
    )

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🟦 Mini Twitter (Streamlit)")

if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------- AUTH UI --------
if st.session_state.user_id is None:
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            uid = login(u, p)
            if uid:
                st.session_state.user_id = uid
                st.rerun()
            else:
                st.error("Invalid login")

    with tab2:
        e = st.text_input("Email")
        u = st.text_input("New Username")
        p = st.text_input("New Password", type="password")
        if st.button("Register"):
            uid = register(e, u, p)
            if uid:
                st.success("Account created! Please log in.")
            else:
                st.error("Username already taken")

# -------- MAIN APP --------
else:
    uid = st.session_state.user_id
    st.success(f"Logged in as {users[uid]['username']}")

    if st.button("Log out"):
        st.session_state.user_id = None
        st.rerun()

    st.divider()

    # Create Tweet
    tweet_text = st.text_area("What's happening?", max_chars=280)
    if st.button("Tweet"):
        try:
            create_tweet(uid, tweet_text)
            st.rerun()
        except:
            st.error("Tweet blocked by moderation")

    st.divider()

    # Feed
    st.subheader("Feed")
    for t in home_feed(uid):
        st.write(f"**@{users[t.author_id]['username']}**")
        st.write(t.content)
        st.write(f"❤️ {len(t.likes)}")
        if st.button("Like", key=t.id):
            like_tweet(uid, t.id)
            st.rerun()
        st.divider()
