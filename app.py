from flask import Flask, render_template, request, jsonify
import os, json, urllib.parse, requests, random
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = "static/uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs("maps", exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

# Googleサジェスト
@app.route("/api/related", methods=["POST"])
def related_words():
    data = request.json
    word = data.get("word", "").strip()
    if not word:
        return jsonify({"ok": False, "error": "word not provided"})
    try:
        url = "http://suggestqueries.google.com/complete/search"
        params = {"client": "firefox", "q": word, "hl": "ja"}
        res = requests.get(url, params=params)
        suggestions = res.json()[1]
        cleaned = []
        for s in suggestions:
            if s.startswith(word):
                rest = s.replace(word, "").strip()
                if rest:
                    cleaned.append(rest)
            else:
                cleaned.append(s)
        return jsonify({"ok": True, "related": cleaned[:3]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# いらすとや検索
@app.route("/api/image", methods=["POST"])
def image_search():
    data = request.json
    word = data.get("word", "").strip()
    if not word:
        return jsonify({"ok": False, "error": "word not provided"})
    try:
        query = urllib.parse.quote(word)
        url = f"https://www.irasutoya.com/search?q={query}&m=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        img_tags = soup.select("img")
        if len(img_tags) >= 15:
            img_tag = random.choice(img_tags[1:15])
        elif img_tags:
            img_tag = img_tags[0]
        else:
            return jsonify({"ok": False, "error": "画像が見つかりません"})
        img_url = img_tag.get("src") or img_tag.get("data-src")
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            img_url = "https://www.irasutoya.com" + img_url
        return jsonify({"ok": True, "url": img_url})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# Wikipedia要約取得
# Wikipedia概要取得（冒頭1～2文）
@app.route("/api/wiki", methods=["POST"])
def wiki_summary():
    req_data = request.json
    word = req_data.get("word", "").strip()
    if not word:
        return jsonify({"ok": False, "error": "word not provided"})
    try:
        url = f"https://ja.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(word)}"
        headers = {"User-Agent": "MindmapApp/1.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return jsonify({"ok": False, "error": f"Wikipedia not found ({res.status_code})"})
        wiki_data = res.json()
        summary = wiki_data.get("extract") or ""
        sentences = [s for s in summary.split("。") if s.strip()]
        if sentences:
            short_summary = "。\n".join(sentences[:2]).strip(" 。\n") + "。"
        else:
            short_summary = "説明文が見つかりませんでした"
        return jsonify({"ok": True, "summary": short_summary})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# Googleサジェスト関連ワード取得
@app.route("/api/related", methods=["POST"])
def related():
    req_data = request.json
    word = req_data.get("word", "").strip()
    if not word:
        return jsonify({"ok": False, "error": "word not provided"})
    try:
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q={urllib.parse.quote(word)}"
        res = requests.get(url, timeout=5)
        suggestions = res.json()[1]
        return jsonify({"ok": True, "related": suggestions[:10]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# マップ保存
@app.route("/map/save", methods=["POST"])
def save_map():
    data = request.json
    filename = data.pop("filename", "map") + ".json"
    try:
        with open(os.path.join("maps", filename), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# マップ一覧
@app.route("/maps")
def map_list():
    files = [f for f in os.listdir("maps") if f.endswith(".json")]
    return jsonify(files)

# マップロード
@app.route("/map/load/<filename>")
def map_load(filename):
    try:
        with open(os.path.join("maps", filename), "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

# 手動画像アップロード
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "ファイルなし"})
    fname = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    file.save(path)
    return jsonify({"ok": True, "url": "/static/uploads/" + fname})

# 使用ログ記録
import time
from datetime import datetime

LOG_FILE = "logs.json"
os.makedirs("logs", exist_ok=True)
def save_log(entry):
    try:
        path = os.path.join("logs", LOG_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
        data.append(entry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("ログ保存失敗:", e)

@app.route("/log/start", methods=["POST"])
def log_start():
    info = request.json
    entry = {
        "event": "start",
        "user": info.get("user", "guest"),
        "map": info.get("map", ""),
        "time": datetime.now().isoformat()
    }
    save_log(entry)
    return jsonify({"ok": True})

@app.route("/log/end", methods=["POST"])
def log_end():
    info = request.json
    entry = {
        "event": "end",
        "user": info.get("user", "guest"),
        "map": info.get("map", ""),
        "time": datetime.now().isoformat()
    }
    save_log(entry)
    return jsonify({"ok": True})

@app.route("/logs")
def view_logs():
    path = os.path.join("logs", LOG_FILE)
    if not os.path.exists(path):
        return jsonify([])
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5008)
