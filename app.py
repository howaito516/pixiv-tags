from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date
import os

app = Flask(__name__)

# --- DB 接続 ---
def get_db():
    conn = sqlite3.connect("tags.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- 初回起動時にテーブル作成 ---
with get_db() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_search DATE NOT NULL
        )
    """)

# --- トップページ（タグ一覧） ---
@app.route("/")
def index():
    db = get_db()
    tags = db.execute("SELECT * FROM tags").fetchall()
    return render_template("index.html", tags=tags)

# --- タグ追加 ---
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form["name"]
        today = date.today().isoformat()
        db = get_db()
        db.execute("INSERT INTO tags (name, last_search) VALUES (?, ?)", (name, today))
        db.commit()
        return redirect("/")
    return render_template("add.html")

# --- 検索して last_search を更新 ---
@app.route("/search/<int:tag_id>")
def search(tag_id):
    db = get_db()
    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()

    # pixiv 検索 URL
    url = f"https://www.pixiv.net/tags/{tag['name']}/artworks"

    # 最終検索日を今日に更新
    db.execute("UPDATE tags SET last_search = ? WHERE id = ?", (date.today().isoformat(), tag_id))
    db.commit()

    return redirect(url)

# --- Flask 起動（Render 用） ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
