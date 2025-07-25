from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
import uuid
from datetime import datetime
from pytz import timezone
import base64
import tempfile
import asyncio
import sacad
from sacad.cover import CoverImageFormat

app = Flask(__name__)
CORS(app)

# Your three‑button HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Family Radio Feeds</title>
  <style>
    body { font-family: sans-serif; text-align: center; padding-top: 4rem; }
    .button {
      display: inline-block; margin: 1rem; padding: 1rem 2rem;
      font-size: 1.25rem; background-color: #0077cc; color: white;
      text-decoration: none; border-radius: 0.5rem;
    }
    .button:hover { background-color: #005fa3; }
  </style>
</head>
<body>
  <h1>Family Radio JSON Feeds</h1>
  <a class="button" href="/east-feed.json" target="_blank">East Feed (WFME)</a>
  <a class="button" href="/west-feed.json" target="_blank">West Feed (KEAR)</a>
  <a class="button" href="/worship-feed.json" target="_blank">Worship Feed</a>
  <a class="button" href="/fourth-feed.json" target="_blank">Fourth Feed</a>
  <a class="button" href="/fifth-feed.json" target="_blank">Fifth Feed</a>
</body>
</html>
'''

# Upstream sources
SOURCE_EAST   = "https://yp.cdnstream1.com/metadata/2632_128/last/12.json"
SOURCE_WEST   = "https://yp.cdnstream1.com/metadata/2638_128/last/12.json"
SOURCE_THIRD  = "https://yp.cdnstream1.com/metadata/2878_128/last/12.json"
SOURCE_FOURTH = ""  # TODO: update with real URL
SOURCE_FIFTH  = ""  # TODO: update with real URL

def fetch_tracks(source_url):
    try:
        r = requests.get(source_url, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] Fetch failed for {source_url}: {e}")
        return []

def lookup_album_art(artist, album):
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                sacad.search_and_download(
                    album,
                    artist,
                    CoverImageFormat.JPEG,
                    450,
                    tmp.name,
                    size_tolerance_prct=25,
                )
            )
            loop.close()
            if success:
                with open(tmp.name, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                return {"imageUrl": f"data:image/jpeg;base64,{img_b64}", "itunesTrackUrl": "", "previewUrl": ""}
    except Exception as e:
        print(f"[WARN] SACAD lookup failed: {e}")
    return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}

def to_spec_format(raw_tracks):
    central = timezone("America/Chicago")
    out = []
    for idx, t in enumerate(raw_tracks):
        artist = t.get("TPE1","Family Radio")
        title  = t.get("TIT2","")
        album  = t.get("TALB", title)
        start  = t.get("start_time", datetime.now().timestamp())
        ts     = datetime.fromtimestamp(start, tz=central).isoformat()
        if artist.strip().lower() == "family radio" or title.strip().lower() == "family radio":
            meta = {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}
        else:
            meta   = lookup_album_art(artist, album)
        out.append({
            "id": str(uuid.uuid4()),
            "artist": artist,
            "title": title,
            "album": t.get("TALB",""),
            "time": ts,
            "imageUrl": meta["imageUrl"],
            "itunesTrackUrl": meta["itunesTrackUrl"],
            "previewUrl": meta["previewUrl"],
            "duration": t.get("duration","00:03:00"),
            "status": "playing" if idx==0 else "history",
            "type": "song"
        })
    return out

# -------------- ROUTES -----------------

@app.route("/")
def homepage():
    return render_template_string(HTML_TEMPLATE)

@app.route("/east-feed.json")
def feed_east():
    data = fetch_tracks(SOURCE_EAST)
    return jsonify({"nowPlaying": to_spec_format(data)})

@app.route("/west-feed.json")
def feed_west():
    data = fetch_tracks(SOURCE_WEST)
    return jsonify({"nowPlaying": to_spec_format(data)})

@app.route("/worship-feed.json")
def feed_worship():
    data = fetch_tracks(SOURCE_THIRD)
    return jsonify({"nowPlaying": to_spec_format(data)})

@app.route("/fourth-feed.json")
def feed_fourth():
    data = fetch_tracks(SOURCE_FOURTH)
    return jsonify({"nowPlaying": to_spec_format(data)})

@app.route("/fifth-feed.json")
def feed_fifth():
    data = fetch_tracks(SOURCE_FIFTH)
    return jsonify({"nowPlaying": to_spec_format(data)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
