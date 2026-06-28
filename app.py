from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from datetime import datetime, timedelta, timezone
import os
import csv
import io
import urllib.parse

app = Flask(__name__)

# --- JST設定 ---
JST = timezone(timedelta(hours=9))
def today_jst():
    return datetime.now(JST).date().isoformat()

# --- DB接続 ---
def get_db():
    conn = sqlite3.connect("tags.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- テーブル作成 ---
with get_db() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_search DATE NOT NULL,
            memo TEXT
        )
    """)

# --- CSV日付強化版 ---
def normalize_date(raw):
    if not raw:
        return today_jst()

    raw = raw.strip().replace("/", "-")

    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass

    parts = raw.split("-")

    if len(parts) == 3 and len(parts[0]) == 4:
        return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

    if len(parts) == 3 and len(parts[0]) == 2:
        return f"20{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

    if len(parts) == 2:
        year = today_jst().split("-")[0]
        return f"{year}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"

    return today_jst()

# --- CSV永続化 ---
CSV_PATH = "tags.csv"

def export_to_csv():
    db = get_db()
    tags = db.execute("SELECT name, last_search, memo FROM tags").fetchall()
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["タグ名", "最終検索日", "メモ"])
        for tag in tags:
            writer.writerow([tag["name"], tag["last_search"], tag["memo"]])

def import_from_csv():
    if not os.path.exists(CSV_PATH):
        return
    db = get_db()
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
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

# --- 起動時にCSV読み込み ---
import_from_csv()

# --- トップページ ---
@app.route("/")
def index():
    sort = request.args.get("sort", "desc")
    db = get_db()
    tags = db.execute(
        f"SELECT * FROM tags ORDER BY last_search {'ASC' if sort=='asc' else 'DESC'}"
    ).fetchall()
    return render_template("index.html", tags=tags, sort=sort)

# --- タグ追加 ---
@app.route("/add", methods=["POST"])
def add():
    name = request.form["name"]
    memo = request.form["memo"]
    today = today_jst()

    db = get_db()
    db.execute(
        "INSERT INTO tags (name, last_search, memo) VALUES (?, ?, ?)",
        (name, today, memo)
    )
    db.commit()
    export_to_csv()
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
        export_to_csv()
        return redirect("/")

    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
    return render_template("edit.html", tag=tag)

# --- タグ削除 ---
@app.route("/delete/<int:tag_id>", methods=["POST"])
def delete(tag_id):
    db = get_db()
    db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    db.commit()
    export_to_csv()
    return redirect("/")

# --- 重複削除（メモ長優先） ---
@app.route("/dedupe", methods=["POST"])
def dedupe():
    db = get_db()
    tags = db.execute("SELECT * FROM tags").fetchall()

    grouped = {}
    for tag in tags:
        grouped.setdefault(tag["name"], []).append(tag)

    for name, items in grouped.items():
        if len(items) <= 1:
            continue

        newest = max(items, key=lambda x: x["last_search"])
        longest_memo = max(items, key=lambda x: len(x["memo"] or ""))

        db.execute(
            "UPDATE tags SET last_search = ?, memo = ? WHERE id = ?",
            (newest["last_search"], longest_memo["memo"], newest["id"])
        )

        for tag in items:
            if tag["id"] != newest["id"]:
                db.execute("DELETE FROM tags WHERE id = ?", (tag["id"],))

    db.commit()
    export_to_csv()
    return redirect("/")

# --- Pixiv公式アプリでタグ検索を開く ---
@app.route("/search/<int:tag_id>")
def search(tag_id):
    db = get_db()
    tag = db.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()

    # タグ名をURLエンコード（日本語対応）
    tag_encoded = urllib.parse.quote(tag["name"])

    # Pixiv公式アプリ Deep Link
    url = f"pixiv://search?tag={tag_encoded}"

    # 最終検索日更新
    today = today_jst()
    db.execute("UPDATE tags SET last_search = ? WHERE id = ?", (today, tag_id))
    db.commit()
    export_to_csv()

    return redirect(url)

# --- CSVインポート ---
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
    export_to_csv()
    return redirect("/")

# --- CSVダウンロード ---
@app.route("/download")
def download():
    if not os.path.exists(CSV_PATH):
        export_to_csv()
    return send_file(
        CSV_PATH,
        mimetype="text/csv",
        as_attachment=True,
        download_name="tags.csv"
    )

# --- Flask起動（Render対応） ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
