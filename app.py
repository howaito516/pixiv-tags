from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from datetime import date, datetime
import os
import csv
import io

app = Flask(__name__)

# --- DB 接続 ---
def get_db():
    conn = sqlite3.connect("tags.db", check_same_thread=False)
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

# --- 日付を YYYY-MM-DD に正規化（ゼロ埋め対応） ---
def normalize_date(raw):
    if not raw:
        return date.today().isoformat()

    raw = raw.replace("/", "-")

    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        parts = raw.split("-")
        if len(parts) == 3:
            y = parts[0]
            m = parts[1].zfill(2)
            d = parts[2].zfill(2)
            return f"{y}-{m}-{d}"
    return date.today().isoformat()

# --- トップページ ---
@app.route("/")
def index():
    sort = request.args.get("sort", "desc")
    db = get_db()

    if sort == "asc":
        tags = db.execute("SELECT * FROM tags ORDER BY last_search ASC").fetchall()
    else:
        tags = db.execute("SELECT * FROM tags ORDER BY last_search DESC").fetchall()

    return render_template("index.html", tags=tags, sort=sort)

# --- タグ追加 ---
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

# --- 検索（前回検索日 → 今日まで） ---
@app.route("/search/<int:tag_id>")
def search(tag_id):
    db = get_db()

    # ① DBからタグ情報を取得
    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()

    # ② 前回検索日（開始日）
    start = normalize_date(tag["last_search"])

    # ③ 今日（終了日）
    today = date.today().isoformat()

    # ④ 最終検索日時～本日までのURLを作成（あなたの①）
    url = (
        f"https://www.pixiv.net/search?"
        f"q={tag['name']}&s_mode=tag&type=artwork&scd={start}&ecd={today}"
    )

    # ⑤ DB上の最終検索日時を本日に更新（あなたの②）
    db.execute("UPDATE tags SET last_search = ? WHERE id = ?", (today, tag_id))
    db.commit()

    print(f"[INFO] URL created: {url}")
    print(f"[INFO] Updated last_search for tag_id={tag_id} to {today}")

    # ⑥ URLに飛ぶ（あなたの③）
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

    next(reader, None)

    db = get_db()
    for row in reader:
        if len(row) >= 2:
            name = row[0]
            last_search = normalize_date(row[1])
            memo = row[2] if len(row) >= 3 else ""
            db.execute(
                "INSERT INTO tags (name, last_search, memo) VALUES (?, ?, ?)",
                (name, last_search, memo)
            )
    db.commit()

    return redirect("/")

# --- キャッシュ無効化（戻るボタンでも最新表示） ---
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- Flask 起動 ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
