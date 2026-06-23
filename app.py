from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import requests
import random
import datetime
import hashlib
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "classic_compass_super_secret_key"

DB_FILE = "compass.db"
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_random_global_artwork():
    try:
        search_url = "https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&departmentId=11"
        res = requests.get(search_url, timeout=4).json()
        if res.get("objectIDs"):
            random_id = random.choice(res["objectIDs"][:300])
            object_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{random_id}"
            obj_res = requests.get(object_url, timeout=4).json()
            if obj_res.get("primaryImage"):
                return {
                    "url": obj_res["primaryImage"],
                    "title": obj_res.get("title", "Untitled Masterpiece"),
                    "artist": obj_res.get("artistDisplayName", "Unknown Master Artisan")
                }
    except Exception: pass
    return {
        "url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?q=80&w=1000",
        "title": "Classic Oil Canvas",
        "artist": "Renaissance Master"
    }

def update_global_canvas_if_expired():
    conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
    row = cursor.execute("SELECT last_sync, image_url, art_title, art_artist FROM canvas_scheduler LIMIT 1").fetchone()
    now = datetime.datetime.now()
    
    if row is None:
        art = get_random_global_artwork()
        cursor.execute("INSERT INTO canvas_scheduler (last_sync, image_url, art_title, art_artist) VALUES (?, ?, ?, ?)", (now.isoformat(), art["url"], art["title"], art["artist"]))
        conn.commit(); conn.close(); return art
    
    if (now - datetime.datetime.fromisoformat(row[0])).total_seconds() >= 43200: 
        new_art = get_random_global_artwork()
        cursor.execute("UPDATE canvas_scheduler SET last_sync = ?, image_url = ?, art_title = ?, art_artist = ? WHERE id = 1", (now.isoformat(), new_art["url"], new_art["title"], new_art["artist"]))
        conn.commit(); conn.close(); return new_art
    
    conn.close()
    return {"url": row[1], "title": row[2], "artist": row[3]}

def init_db():
    conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_stats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE, streak INTEGER DEFAULT 0, pages_this_week INTEGER DEFAULT 0, classics_completed INTEGER DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id))")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, 
            author TEXT, 
            days_until_start INTEGER DEFAULT 7, 
            is_featured INTEGER DEFAULT 0, 
            cover_url TEXT DEFAULT ''
        )
    """)
    
    if cursor.execute("SELECT * FROM books").fetchone() is None:
        cursor.execute("""
            INSERT INTO books (title, author, days_until_start, is_featured, cover_url) 
            VALUES ('Jane Eyre', 'Charlotte Brontë', 7, 1, 'https://covers.openlibrary.org/b/id/14589005-L.jpg')
        """)
        
    cursor.execute("CREATE TABLE IF NOT EXISTS vocabulary_vault (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, book_id INTEGER, word TEXT, meaning TEXT, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(book_id) REFERENCES books(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS buddy_reads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, book_id INTEGER, UNIQUE(user_id, book_id), FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(book_id) REFERENCES books(id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS tbr_list (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, book_id INTEGER, UNIQUE(user_id, book_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS book_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, book_id INTEGER, review_text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS canvas_scheduler (id INTEGER PRIMARY KEY AUTOINCREMENT, last_sync TEXT, image_url TEXT, art_title TEXT, art_artist TEXT)")
    
    # Locket App Shared Moments Storage Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_moments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            image_url TEXT,
            caption TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit(); conn.close()

init_db()

@app.route("/")
def home():
    canvas = update_global_canvas_if_expired()
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    
    stats = cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (session.get("user_id"),)).fetchone() if "user_id" in session else {"streak": 0, "pages_this_week": 0, "classics_completed": 0}
    
    # Clean initial state configuration (No books loaded until searched)
    featured_book = None
    days_left = ""
    saved_words = []
    buddies = []
    reviews = []
    is_joined = False
    dynamic_reader_count = 0
    
    # Fetch uploaded Locket moments
    moments = cursor.execute("SELECT * FROM shared_moments ORDER BY timestamp DESC LIMIT 6").fetchall()
    conn.close()
    
    return render_template("home.html", stats=stats, book=featured_book, words=saved_words, buddies=buddies, is_joined=is_joined, reviews=reviews, canvas=canvas, reader_count=dynamic_reader_count, days_left=days_left, moments=moments)

@app.route("/search", methods=["GET"])
def search_book():
    canvas = update_global_canvas_if_expired()
    search_query = request.args.get("query", "").strip()
    if not search_query: return redirect(url_for("home"))

    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    found_book = cursor.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ?", (f"%{search_query}%", f"%{search_query}%")).fetchone()
    
    if not found_book:
        try:
            api_url = f"https://openlibrary.org/search.json?title={search_query}&fields=title,author_name,cover_i,first_publish_year"
            doc = requests.get(api_url, timeout=5).json()["docs"][0]
            publish_year = doc.get("first_publish_year", 2000) 
            
            if publish_year <= 1960:
                title, author = doc.get("title", "Unknown Title"), doc.get("author_name", ["Unknown Author"])[0]
                cover_id = doc.get("cover_i")
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else ""
                
                cursor.execute("INSERT INTO books (title, author, days_until_start, is_featured, cover_url) VALUES (?, ?, 7, 0, ?)", (title, author, cover_url))
                conn.commit()
                found_book = cursor.execute("SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)).fetchone()
            else:
                session["search_error"] = f"'{doc.get('title')}' was published in {publish_year}. Only classics published before 1960 are allowed!"
                conn.close()
                return redirect(url_for("home"))
        except Exception: pass 
            
    stats = cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (session.get("user_id"),)).fetchone() if "user_id" in session else {"streak": 0, "pages_this_week": 0, "classics_completed": 0}
    
    # Synchronized Calendar Countdown Logic
    target_date = datetime.date(2026, 6, 30)
    diff = (target_date - datetime.date.today()).days
    days_left = "Cycle Ended" if diff < 0 else f"{diff} days left"
    
    moments = cursor.execute("SELECT * FROM shared_moments ORDER BY timestamp DESC LIMIT 6").fetchall()
    
    saved_words, buddies, reviews, is_joined, dynamic_reader_count = [], [], [], False, 0
    if found_book:
        if "user_id" in session:
            is_joined = cursor.execute("SELECT 1 FROM buddy_reads WHERE user_id = ? AND book_id = ?", (session["user_id"], found_book["id"])).fetchone() is not None
            saved_words = cursor.execute("SELECT * FROM vocabulary_vault WHERE user_id = ? AND book_id = ?", (session["user_id"], found_book["id"])).fetchall()
        
        buddies = cursor.execute("SELECT users.username FROM buddy_reads INNER JOIN users ON buddy_reads.user_id = users.id WHERE buddy_reads.book_id = ?", (found_book["id"],)).fetchall()
        reviews = cursor.execute("SELECT book_reviews.*, users.username FROM book_reviews INNER JOIN users ON book_reviews.user_id = users.id WHERE book_reviews.book_id = ? ORDER BY book_reviews.timestamp DESC", (found_book["id"],)).fetchall()
        
        count_res = cursor.execute("SELECT COUNT(*) FROM buddy_reads WHERE book_id = ?", (found_book["id"],)).fetchone()
        dynamic_reader_count = count_res[0] if count_res else 0
        
    conn.close()
    if found_book:
        return render_template("home.html", stats=stats, book=found_book, words=saved_words, buddies=buddies, is_joined=is_joined, reviews=reviews, canvas=canvas, reader_count=dynamic_reader_count, days_left=days_left, moments=moments)
    return redirect(url_for("home"))

@app.route("/upload_moment", methods=["POST"])
def upload_moment():
    if "username" not in session: return "Please login first!"
    file = request.files.get("moment_image")
    caption = request.form.get("caption", "").strip()
    
    if file and file.filename != '':
        filename = secure_filename(f"{datetime.datetime.now().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_url = f"/static/uploads/{filename}"
        
        conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        cursor.execute("INSERT INTO shared_moments (username, image_url, caption) VALUES (?, ?, ?)", (session["username"], image_url, caption))
        conn.commit(); conn.close()
    return redirect(url_for("home"))

@app.route("/join_buddy/<int:book_id>", methods=["POST"])
def join_buddy(book_id):
    if "user_id" not in session: return "Please login first!"
    conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO buddy_reads (user_id, book_id) VALUES (?, ?)", (session["user_id"], book_id))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for("home"))

@app.route("/add_review/<int:book_id>", methods=["POST"])
def add_review(book_id):
    if "user_id" not in session: return "Please login first!"
    review_text = request.form.get("review_text", "").strip()
    if not review_text: return redirect(request.referrer or url_for("home"))
    conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
    cursor.execute("INSERT INTO book_reviews (user_id, book_id, review_text) VALUES (?, ?, ?)", (session["user_id"], book_id, review_text))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for("home"))

@app.route("/add_word", methods=["POST"])
def add_word():
    if "user_id" not in session: return "Please login first!"
    word, meaning, book_id = request.form.get("word").strip(), request.form.get("meaning").strip(), request.form.get("book_id")
    conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
    cursor.execute("INSERT INTO vocabulary_vault (user_id, book_id, word, meaning) VALUES (?, ?, ?, ?)", (session["user_id"], book_id, word, meaning))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username, password = request.form.get("username").strip(), request.form.get("password")
        conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
            cursor.execute("INSERT INTO user_stats (user_id, streak, pages_this_week, classics_completed) VALUES (?, 0, 0, 0)", (cursor.lastrowid,))
            conn.commit(); return redirect(url_for("login"))
        except sqlite3.IntegrityError: return "Username already exists!"
        finally: conn.close()
    return render_template("login.html", action="Register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = request.form.get("username").strip(), request.form.get("password")
        conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_password(password))).fetchone()
        conn.close()
        if user: session["user_id"], session["username"] = user["id"], user["username"]; return redirect(url_for("home"))
        return "Invalid credentials!"
    return render_template("login.html", action="Login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)