from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from datetime import date
import os
import csv
import io

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
            last_search DATE NOT NULL,
            memo TEXT
        )
    """)

# --- トップページ（タグ一覧 + ソート + 追加フォーム） ---
@app.route("/")
def index():
    sort = request.args.get("sort", "desc")

    db = get_db()
    if sort == "asc":
        tags = db.execute("SELECT * FROM tags ORDER BY last_search ASC").fetchall()
    else:
        tags = db.execute("SELECT * FROM tags ORDER BY last_search DESC").fetchall()

    return render_template("index.html", tags=tags, sort=sort)

# --- タグ追加（トップページからPOST） ---
@app.route("/add", methods=["POST"])
def add():
    name = request.form["name"]
    memo = request.form["memo"]
    today = date.today().isoformat()

    db = get_db()
    db.execute(
        "INSERT INTO tags (name, last_search, memo) VALUES (?, ?, ?)",
        (name, today, memo)
    )
    db.commit()
    return redirect("/")

# --- タグ編集 ---
@app.route("/edit/<int:tag_id>", methods=["GET", "POST"])
def edit(tag_id):
    db = get_db()

    if request.method == "POST":
        name = request.form["name"]
        memo = request.form["memo"]
        db.execute("UPDATE tags SET name = ?, memo = ? WHERE id = ?", (name, memo, tag_id))
        db.commit()
        return redirect("/")

    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return render_template("edit.html", tag=tag)

# --- タグ削除 ---
@app.route("/delete/<int:tag_id>", methods=["POST"])
def delete(tag_id):
    db = get_db()
    db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    db.commit()
    return redirect("/")

# --- 検索して last_search を更新（scd/ecd対応） ---
@app.route("/search/<int:tag_id>")
def search(tag_id):
    db = get_db()
    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()

    today = date.today().isoformat()
    start = tag["last_search"] or today  # None対策

    # pixivの日付範囲検索URL（YYYY-MM-DD形式）
    url = f"https://www.pixiv.net/tags/{tag['name']}/artworks?scd={start}&ecd={today}"

    # 検索日を更新
    db.execute("UPDATE tags SET last_search = ? WHERE id = ?", (today, tag_id))
    db.commit()

    return redirect(url)

# --- CSV ダウンロード ---
@app.route("/download")
def download():
    db = get_db()
    tags = db.execute("SELECT name, last_search, memo FROM tags").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["タグ名", "最終検索日", "メモ"])

    for tag in tags:
        writer.writerow([tag["name"], tag["last_search"], tag["memo"]])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="pixiv_tags.csv"
    )

# --- CSV インポート ---
@app.route("/import", methods=["POST"])
def import_csv():
    file = request.files["file"]
    if not file:
        return redirect("/")

    stream = io.StringIO(file.stream.read().decode("utf-8-sig"))
    reader = csv.reader(stream)

    next(reader, None)  # ヘッダーをスキップ

    db = get_db()
    for row in reader:
        if len(row) >= 2:
            name = row[0]
            last_search = row[1]
            memo = row[2] if len(row) >= 3 else ""
            db.execute(
                "INSERT INTO tags (name, last_search, memo) VALUES (?, ?, ?)",
                (name, last_search, memo)
            )
    db.commit()

    return redirect("/")

# --- Flask 起動（Render 用） ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
