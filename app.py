import os
import psycopg2
from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime

app = Flask(__name__)

# --- Render 内部 PostgreSQL 接続設定 ---
DB_CONFIG = {
    "host": os.environ.get("SUPABASE_HOST"),
    "database": os.environ.get("SUPABASE_DB"),
    "user": os.environ.get("SUPABASE_USER"),
    "password": os.environ.get("SUPABASE_PASSWORD"),
    "port": int(os.environ.get("SUPABASE_PORT", 5432))
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- テーブル初期化 ---
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            last_search DATE,
            memo TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- トップページ ---
@app.route("/")
def index():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, last_search, memo FROM tags ORDER BY id DESC;")
    tags = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("index.html", tags=tags)

# --- タグ追加 ---
@app.route("/add", methods=["POST"])
def add_tag():
    name = request.form.get("name")
    memo = request.form.get("memo")
    if not name:
        return jsonify({"error": "タグ名が空です"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tags (name, last_search, memo) VALUES (%s, %s, %s);",
        (name, datetime.now().date(), memo)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "タグを追加しました"})

# --- タグ削除 ---
@app.route("/delete/<int:tag_id>", methods=["POST"])
def delete_tag(tag_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tags WHERE id = %s;", (tag_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "タグを削除しました"})

# --- タグ更新 ---
@app.route("/update/<int:tag_id>", methods=["POST"])
def update_tag(tag_id):
    memo = request.form.get("memo")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tags SET memo = %s, last_search = %s WHERE id = %s;",
        (memo, datetime.now().date(), tag_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "タグを更新しました"})

# --- タグ検索（ブラウザ専用） ---
@app.route("/search/<int:tag_id>")
def search_tag(tag_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM tags WHERE id = %s;", (tag_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return "Tag not found", 404

    tag_name = row[0]
    tag_encoded = tag_name.replace(" ", "%20")

    return redirect(f"https://www.pixiv.net/tags/{tag_encoded}/artworks")

# --- CSVインポート ---
@app.route("/import", methods=["POST"])
def import_csv():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "CSVファイルがありません"}), 400

    import csv
    import io

    conn = get_connection()
    cur = conn.cursor()

    reader = csv.reader(io.StringIO(file.stream.read().decode("utf-8")))
    for row in reader:
        if len(row) >= 1:
            name = row[0]
            memo = row[1] if len(row) >= 2 else ""
            cur.execute(
                "INSERT INTO tags (name, last_search, memo) VALUES (%s, %s, %s);",
                (name, datetime.now().date(), memo)
            )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")

# --- Render 用ポート設定 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
