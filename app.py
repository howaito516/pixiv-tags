import os
import psycopg2
from flask import Flask, request, jsonify, render_template, redirect, send_file
from datetime import datetime, timezone, timedelta
import csv
import io

app = Flask(__name__)

# --- 日本標準時（JST） ---
JST = timezone(timedelta(hours=9))

def today_jst():
    return datetime.now(JST).date()

# --- PostgreSQL 接続設定 ---
DB_CONFIG = {
    "host": os.environ.get("SUPABASE_HOST", "localhost"),
    "database": os.environ.get("SUPABASE_DB", "pixiv_tags_db"),
    "user": os.environ.get("SUPABASE_USER", "pixiv_tags_db_user"),
    "password": os.environ.get("SUPABASE_PASSWORD", ""),
    "port": int(os.environ.get("SUPABASE_PORT", 5432)),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- DB初期化 ---
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            memo TEXT,
            last_search DATE
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
    cur.execute("SELECT id, name, memo, last_search FROM tags ORDER BY id DESC;")
    tags = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("index.html", tags=tags)

# --- タグ追加 ---
@app.route("/add", methods=["POST"])
def add_tag():
    name = request.form.get("name")
    memo = request.form.get("memo", "")
    if not name:
        return jsonify({"error": "タグ名が空です"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tags (name, memo, last_search) VALUES (%s, %s, %s);",
        (name, memo, today_jst()),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

# --- タグ削除 ---
@app.route("/delete/<int:tag_id>", methods=["POST"])
def delete_tag(tag_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tags WHERE id = %s;", (tag_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

# --- 全削除 ---
@app.route("/delete_all", methods=["POST"])
def delete_all():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tags;")
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

# --- タグ編集（メモ更新） ---
@app.route("/update/<int:tag_id>", methods=["POST"])
def update_tag(tag_id):
    memo = request.form.get("memo", "")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tags SET memo = %s WHERE id = %s;",
        (memo, tag_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/")

# --- 最終検索日順ソート ---
@app.route("/sort_by_date")
def sort_by_date():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, memo, last_search FROM tags ORDER BY last_search DESC NULLS LAST;")
    tags = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("index.html", tags=tags)

# --- タグ検索（期間指定対応 / 全環境ブラウザ） ---
@app.route("/search/<int:tag_id>")
def search_tag(tag_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, last_search FROM tags WHERE id = %s;", (tag_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return "Tag not found", 404

    tag_name, last_search = row
    today = today_jst()

    # last_search が NULL の場合は今日を開始日にする
    if last_search is None:
        last_search = today

    # 最終検索日を今日に更新
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tags SET last_search = %s WHERE id = %s;",
        (today, tag_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    # URLエンコード（簡易）
    encoded = tag_name.replace(" ", "%20")

    # 期間指定検索URL（Web版Pixiv）
    search_url = (
        f"https://www.pixiv.net/tags/{encoded}/artworks"
        f"?scd={last_search}&ecd={today}"
    )

    return redirect(search_url)

# --- CSVインポート（タグ名 / 最終更新日 / メモ） ---
@app.route("/import", methods=["POST"])
def import_csv():
    file = request.files.get("file")
    if not file:
        return "CSVファイルがありません", 400

    reader = csv.reader(io.StringIO(file.stream.read().decode("utf-8")))

    conn = get_connection()
    cur = conn.cursor()

    for row in reader:
        if len(row) >= 1:
            name = row[0]
            # 最終更新日（YYYY-MM-DD）なければ今日
            if len(row) >= 2 and row[1]:
                try:
                    last_search = datetime.strptime(row[1], "%Y-%m-%d").date()
                except ValueError:
                    last_search = today_jst()
            else:
                last_search = today_jst()
            memo = row[2] if len(row) >= 3 else ""

            cur.execute(
                "INSERT INTO tags (name, memo, last_search) VALUES (%s, %s, %s);",
                (name, memo, last_search),
            )

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/")

# --- CSVエクスポート（タグ名 / 最終更新日 / メモ） ---
@app.route("/export")
def export_csv():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, last_search, memo FROM tags ORDER BY id DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["タグ名", "最終更新日", "メモ"])
    writer.writerows(rows)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"pixiv_tags_{datetime.now(JST).strftime('%Y%m%d')}.csv",
    )

# --- 編集ページ ---
@app.route("/edit/<int:tag_id>")
def edit_page(tag_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, memo, last_search FROM tags WHERE id = %s;", (tag_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return "Tag not found", 404

    return render_template("edit.html", tag=row)

# --- エントリポイント ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
