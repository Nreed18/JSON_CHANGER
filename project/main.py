from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime
from pytz import timezone
import uuid
import httpx
import asyncio
import json
import logging
import redis.asyncio as redis
import hashlib
import requests
import secrets

app = FastAPI()
security = HTTPBasic()

USERNAME = "admin"
PASSWORD = "familyradio2025"

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

rdb = redis.Redis(host="localhost", port=6379, decode_responses=True)

HTML_TEMPLATE = """<!DOCTYPE html>
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
    .admin-button { background-color: #444; }
    .admin-button:hover { background-color: #222; }
  </style>
</head>
<body>
  <h1>Family Radio JSON Feeds</h1>
  <a class="button" href="/east-feed.json" target="_blank">East Feed (WFME)</a>
  <a class="button" href="/west-feed.json" target="_blank">West Feed (KEAR)</a>
  <a class="button" href="/worship-feed.json" target="_blank">Worship Feed</a>
  <a class="button" href="/fourth-feed.json" target="_blank">Fourth Feed</a>
  <a class="button" href="/fifth-feed.json" target="_blank">Fifth Feed</a>
  <br><br>
  <a class="button admin-button" href="/admin/dashboard" target="_blank">📊 Admin Dashboard</a>
  <form action="/admin/test-alert" method="get" target="_blank" style="margin-top: 2rem;">
    <button class="button admin-button">🚨 Send Test Alert</button>
  </form>
</body>
</html>"""

SOURCE_EAST   = "https://yp.cdnstream1.com/metadata/2632_128/last/12.json"
SOURCE_WEST   = "https://yp.cdnstream1.com/metadata/2638_128/last/12.json"
SOURCE_THIRD  = "https://yp.cdnstream1.com/metadata/2878_128/last/12.json"
SOURCE_FOURTH = ""  # TODO: update with real URL
SOURCE_FIFTH  = ""  # TODO: update with real URL

def hash_key(artist: str, title: str) -> str:
    return hashlib.sha1(f"{artist.lower()}|{title.lower()}".encode()).hexdigest()

def get_metrics_keys(feed):
    now = datetime.now()
    return {
        "minute": f"metrics:{feed}:min:{now.strftime('%Y-%m-%d-%H-%M')}",
        "hour": f"metrics:{feed}:hour:{now.strftime('%Y-%m-%d-%H')}",
        "day": f"metrics:{feed}:day:{now.strftime('%Y-%m-%d')}",
        "week": f"metrics:{feed}:week:{now.strftime('%Y-%U')}",
        "month": f"metrics:{feed}:month:{now.strftime('%Y-%m')}",
        "year": f"metrics:{feed}:year:{now.strftime('%Y')}",
    }

def get_unique_keys(feed):
    now = datetime.now()
    return {
        "minute": f"unique:{feed}:min:{now.strftime('%Y-%m-%d-%H-%M')}",
        "hour": f"unique:{feed}:hour:{now.strftime('%Y-%m-%d-%H')}",
        "day": f"unique:{feed}:day:{now.strftime('%Y-%m-%d')}",
        "week": f"unique:{feed}:week:{now.strftime('%Y-%U')}",
        "month": f"unique:{feed}:month:{now.strftime('%Y-%m')}",
        "year": f"unique:{feed}:year:{now.strftime('%Y')}",
    }

async def increment_metrics(feed, client_id):
    keys = get_metrics_keys(feed)
    unique_keys = get_unique_keys(feed)
    pipe = rdb.pipeline()
    for k in keys.values():
        pipe.incr(k)
    for k in unique_keys.values():
        pipe.sadd(k, client_id)
        pipe.expire(k, 1209600)  # Keep unique sets for 14 days
    await pipe.execute()

async def increment_cache_counter(cache_type: str, status: str):
    key = f"metrics:cache:{cache_type}:{status}"
    await rdb.incr(key)

async def fetch_tracks(source_url, ttl=30):
    key = f"feed:{source_url}"
    cached = await rdb.get(key)
    if cached:
        await increment_cache_counter("feed", "hit")
        return json.loads(cached)
    await increment_cache_counter("feed", "miss")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(source_url)
            r.raise_for_status()
            data = r.json()
            await rdb.set(key, json.dumps(data), ex=ttl)
            return data
    except Exception as e:
        logging.error(f"[ERROR] Fetch failed: {e}")
        return []

async def lookup_itunes(artist, title, ttl=300, fail_limit=3):
    hashed = hash_key(artist, title)
    key = f"itunes:{hashed}"
    fail_key = f"fail:{hashed}"
    fails = await rdb.get(fail_key)
    if fails and int(fails) >= fail_limit:
        return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}
    cached = await rdb.get(key)
    if cached:
        await increment_cache_counter("itunes", "hit")
        return json.loads(cached)
    await increment_cache_counter("itunes", "miss")
    query = f"{artist} {title}"
    url = "https://itunes.apple.com/search"
    params = {"term": query, "limit": 1}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            results = r.json().get("results", [])
            if results:
                meta = {
                    "imageUrl": results[0].get("artworkUrl100", "").replace("100x100", "450x450"),
                    "itunesTrackUrl": results[0].get("trackViewUrl", ""),
                    "previewUrl": results[0].get("previewUrl", "")
                }
                await rdb.set(key, json.dumps(meta), ex=ttl)
                return meta
            else:
                await rdb.incr(fail_key)
                await rdb.expire(fail_key, 86400)
                return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}
    except Exception:
        await rdb.incr(fail_key)
        await rdb.expire(fail_key, 86400)
        return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}

async def to_spec_format(raw_tracks):
    central = timezone("America/Chicago")
    tasks = []
    for t in raw_tracks:
        artist = t.get("TPE1", "Family Radio")
        title = t.get("TIT2", "")
        tasks.append(lookup_itunes(artist, title))
    metadatas = await asyncio.gather(*tasks)
    formatted = []
    for idx, (t, meta) in enumerate(zip(raw_tracks, metadatas)):
        artist = t.get("TPE1", "Family Radio")
        title = t.get("TIT2", "")
        track_id = hash_key(artist, title)
        cache_key = f"track_start:{track_id}"
        start_ts = await rdb.get(cache_key)
        if start_ts is None:
            start_ts = str(datetime.now().timestamp())
            await rdb.set(cache_key, start_ts, ex=600)
        ts = datetime.fromtimestamp(float(start_ts), tz=central).isoformat()
        formatted.append({
            "id": str(uuid.uuid4()),
            "artist": artist,
            "title": title,
            "album": t.get("TALB", ""),
            "time": ts,
            "imageUrl": meta["imageUrl"],
            "itunesTrackUrl": meta["itunesTrackUrl"],
            "previewUrl": meta["previewUrl"],
            "duration": t.get("duration", "00:03:00"),
            "status": "playing" if idx == 0 else "history",
            "type": "song"
        })
    return formatted

def get_client_id(request: Request):
    return request.client.host

@app.get("/", response_class=HTMLResponse)
def homepage():
    return HTML_TEMPLATE

@app.get("/east-feed.json")
async def feed_east(request: Request):
    client_id = get_client_id(request)
    await increment_metrics("east", client_id)
    data = await fetch_tracks(SOURCE_EAST)
    return JSONResponse({"nowPlaying": await to_spec_format(data)})

@app.get("/west-feed.json")
async def feed_west(request: Request):
    client_id = get_client_id(request)
    await increment_metrics("west", client_id)
    data = await fetch_tracks(SOURCE_WEST)
    return JSONResponse({"nowPlaying": await to_spec_format(data)})

@app.get("/worship-feed.json")
async def feed_worship(request: Request):
    client_id = get_client_id(request)
    await increment_metrics("worship", client_id)
    data = await fetch_tracks(SOURCE_THIRD)
    return JSONResponse({"nowPlaying": await to_spec_format(data)})

@app.get("/fourth-feed.json")
async def feed_fourth(request: Request):
    client_id = get_client_id(request)
    await increment_metrics("fourth", client_id)
    data = await fetch_tracks(SOURCE_FOURTH)
    return JSONResponse({"nowPlaying": await to_spec_format(data)})

@app.get("/fifth-feed.json")
async def feed_fifth(request: Request):
    client_id = get_client_id(request)
    await increment_metrics("fifth", client_id)
    data = await fetch_tracks(SOURCE_FIFTH)
    return JSONResponse({"nowPlaying": await to_spec_format(data)})

@app.get("/admin/dashboard")
async def admin_dashboard():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def get_feed_metrics(feed):
        keys = get_metrics_keys(feed)
        unique_keys = get_unique_keys(feed)
        values = await rdb.mget(*list(keys.values()))
        unique_vals = []
        for k in unique_keys.values():
            unique_vals.append(await rdb.scard(k))
        periods = ["minute", "hour", "day", "week", "month", "year"]
        return {
            "feed": feed,
            "total": {p: int(values[i] or 0) for i, p in enumerate(periods)},
            "unique": {p: int(unique_vals[i]) for i, p in enumerate(periods)}
        }

    # Check each feed's health
    async def feed_health(url):
        try:
            data = await fetch_tracks(url)
            return (True, data if data else [])
        except Exception:
            return (False, [])

    feeds = ["east", "west", "worship", "fourth", "fifth"]
    feed_urls = [
        SOURCE_EAST,
        SOURCE_WEST,
        SOURCE_THIRD,
        SOURCE_FOURTH,
        SOURCE_FIFTH,
    ]
    metrics = await asyncio.gather(*(get_feed_metrics(f) for f in feeds))
    health_checks = await asyncio.gather(*(feed_health(url) for url in feed_urls))

    # Determine status for each feed
    status_map = {}
    overall_status = "ok"
    for name, (healthy, data) in zip(feeds, health_checks):
        if not healthy or not data:
            status_map[name] = "error"
            overall_status = "error"
        else:
            status_map[name] = "ok"

    cache_feed_keys = await rdb.keys("feed:*")
    cache_itunes_keys = await rdb.keys("itunes:*")

    cache_hit_feed = await rdb.get("metrics:cache:feed:hit") or 0
    cache_miss_feed = await rdb.get("metrics:cache:feed:miss") or 0
    cache_hit_itunes = await rdb.get("metrics:cache:itunes:hit") or 0
    cache_miss_itunes = await rdb.get("metrics:cache:itunes:miss") or 0

    # Include last check times
    last_feed_check = await rdb.get('last_feed_check')
    last_feed_check_east = await rdb.get('last_feed_check:east')
    last_feed_check_west = await rdb.get('last_feed_check:west')
    last_feed_check_worship = await rdb.get('last_feed_check:worship')
    last_feed_check_fourth = await rdb.get('last_feed_check:fourth')
    last_feed_check_fifth = await rdb.get('last_feed_check:fifth')

    return {
        "timestamp": now,
        "feeds": metrics,
        "cache": {
            "feed_keys": len(cache_feed_keys),
            "itunes_keys": len(cache_itunes_keys),
            "hits": {
                "feed": int(cache_hit_feed),
                "itunes": int(cache_hit_itunes),
            },
            "misses": {
                "feed": int(cache_miss_feed),
                "itunes": int(cache_miss_itunes),
            }
        },
        "status": overall_status,
        "feed_status": status_map,
        "last_feed_check": last_feed_check,
        "last_feed_check_east": last_feed_check_east,
        "last_feed_check_west": last_feed_check_west,
        "last_feed_check_worship": last_feed_check_worship,
        "last_feed_check_fourth": last_feed_check_fourth,
        "last_feed_check_fifth": last_feed_check_fifth
    }

@app.get("/admin/test-alert")
async def trigger_test_alert(credentials: HTTPBasicCredentials = Depends(security)):
    if not (
        secrets.compare_digest(credentials.username, USERNAME) and
        secrets.compare_digest(credentials.password, PASSWORD)
    ):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    pagerduty_key = "be2800efd3ac410fc05d30cea86764f9"
    payload = {
        "routing_key": pagerduty_key,
        "event_action": "trigger",
        "payload": {
            "summary": "🚨 Manual test alert triggered from FastAPI admin page",
            "severity": "info",
            "source": "admin-dashboard",
            "component": "fastapi-app"
        },
        "dedup_key": "manual-admin-test"
    }

    try:
        r = requests.post("https://events.pagerduty.com/v2/enqueue", json=payload, timeout=5)
        return {"status": "sent", "response": r.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}
