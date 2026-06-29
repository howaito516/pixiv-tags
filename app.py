from flask import Flask, request, render_template, redirect, send_file
import psycopg2
from datetime import datetime, timezone, timedelta
import os
import csv
import io

app = Flask(__name__)

# -----------------------------
#  日本標準時（JST）
# -----------------------------
JST = timezone(timedelta(hours=9))

def today_jst():
    return datetime.now(JST).date()


# -----------------------------
#  DB接続設定
# -----------------------------
DB_CONFIG = {
    "host": os.environ.get("SUPABASE_HOST", "localhost"),
    "database": os.environ.get("SUPABASE_DB", "pixiv_tags_db"),
    "user": os.environ.get("SUPABASE_USER", "pixiv_tags_db_user"),
    "password": os.environ.get("SUPABASE_PASSWORD", ""),
    "port": int(os.environ.get("SUPABASE_PORT", 5432)),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# -----------------------------
#  DB初期化（tagsテーブル）
# -----------------------------
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


# -----------------------------
#  トップページ
# -----------------------------
@app.route("/")
def index():
    # TODO: タグ一覧取得
    return render_template("index.html", tags=[])


# -----------------------------
#  タグ追加
# -----------------------------
@app.route("/add", methods=["POST"])
def add_tag():
    name = request.form.get("name", "").strip()
    memo = request.form.get("memo", "").strip()

    if not name:
        return "タグ名が空です", 400

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


# -----------------------------
#  タグ削除
# -----------------------------
@app.route("/delete/<int:tag_id>", methods=["POST"])
def delete_tag(tag_id):
    # TODO: タグ削除処理
    return redirect("/")


# -----------------------------
#  全削除
# -----------------------------
@app.route("/delete_all", methods=["POST"])
def delete_all():
    # TODO: 全削除処理
    return redirect("/")


# -----------------------------
#  タグ編集ページ
# -----------------------------
@app.route("/edit/<int:tag_id>")
def edit_page(tag_id):
    # TODO: 編集ページ表示
    return render_template("edit.html", tag=None)


# -----------------------------
#  タグ更新（メモ編集）
# -----------------------------
@app.route("/update/<int:tag_id>", methods=["POST"])
def update_tag(tag_id):
    # TODO: メモ更新処理
    return redirect("/")


# -----------------------------
#  最終更新日順ソート
# -----------------------------
@app.route("/sort_by_date")
def sort_by_date():
    # TODO: ソート処理
    return render_template("index.html", tags=[])


# -----------------------------
#  タグ検索（Pixivへ飛ぶ）
# -----------------------------
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

    if last_search is None:
        last_search = today

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tags SET last_search = %s WHERE id = %s;",
        (today, tag_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    encoded = tag_name.replace(" ", "%20")
    url = f"https://www.pixiv.net/tags/{encoded}/artworks?scd={last_search}&ecd={today}"

    return redirect(url)


# -----------------------------
#  CSVインポート
# -----------------------------
@app.route("/import", methods=["POST"])
def import_csv():
    # TODO: CSV読み込み → DB登録
    return redirect("/")


# -----------------------------
#  CSVエクスポート
# -----------------------------
@app.route("/export")
def export_csv():
    # TODO: DB取得 → CSV生成 → send_file
    return send_file(io.BytesIO(b""), mimetype="text/csv")


# -----------------------------
#  エントリポイント
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
