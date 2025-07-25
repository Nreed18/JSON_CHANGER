from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime
from pytz import timezone
import uuid
import httpx
import asyncio
import json
import logging
import os
import csv
import redis.asyncio as redis
import hashlib
import requests
import secrets
import functools
import sacad
from sacad.cover import CoverSourceResult

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

USERNAME = os.getenv("ADMIN_USER", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "familyradio2025")
PAGERDUTY_KEY = os.getenv("PD_ROUTING_KEY", "be2800efd3ac410fc05d30cea86764f9")

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
rdb = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# CSV file used for album lookup. Can be overridden with environment variable.
ALBUM_LOOKUP_CSV = os.getenv("ALBUM_LOOKUP_CSV", "album_lookup.csv")

# In-memory mapping {(artist_lower, title_lower): album}
album_lookup = {}

# Flag to indicate if Redis is available. If connection fails on startup the
# application will still run but caching/metrics will be disabled.
rdb_available = True

@app.on_event("startup")
async def check_redis_connection():
    global rdb, rdb_available
    try:
        await rdb.ping()
    except Exception as e:
        logging.warning(f"Redis unavailable: {e}. Running without cache/metrics.")
        rdb = None
        rdb_available = False
    # Load CSV after Redis check so we don't block startup
    load_album_lookup(ALBUM_LOOKUP_CSV)

def load_album_lookup(path: str):
    """Load CSV mapping of artist+title to album."""
    global album_lookup
    if not os.path.exists(path):
        logging.warning(f"Album lookup CSV not found at {path}")
        album_lookup = {}
        return
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip().lower()
                artist = row.get('artist', '').strip().lower()
                album = row.get('album', '').strip()
                if title and artist and album:
                    album_lookup[(artist, title)] = album
        logging.info(f"Loaded {len(album_lookup)} album entries from {path}")
    except Exception as e:
        logging.error(f"Failed to load album lookup CSV: {e}")
        album_lookup = {}

def get_csv_album(artist: str, title: str) -> str:
    """Return album from lookup CSV if present."""
    return album_lookup.get((artist.lower(), title.lower()), '')

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
    if not rdb_available:
        return
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
    if not rdb_available:
        return
    key = f"metrics:cache:{cache_type}:{status}"
    await rdb.incr(key)

async def fetch_tracks(source_url, ttl=30):
    key = f"feed:{source_url}"
    if rdb_available:
        try:
            cached = await rdb.get(key)
        except Exception:
            cached = None
    else:
        cached = None
    if cached:
        await increment_cache_counter("feed", "hit")
        return json.loads(cached)
    await increment_cache_counter("feed", "miss")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(source_url)
            r.raise_for_status()
            data = r.json()
            if rdb_available:
                try:
                    await rdb.set(key, json.dumps(data), ex=ttl)
                except Exception:
                    pass
            return data
    except Exception as e:
        logging.error(f"[ERROR] Fetch failed: {e}")
        return []

async def sacad_search_url(artist: str, album: str, size: int = 450, tol: int = 25) -> str:
    """Return the first artwork URL from SACAD without downloading."""
    source_classes = tuple(sacad.COVER_SOURCE_CLASSES.values())
    cover_sources = [cls(size, tol) for cls in source_classes]
    search_futs = [asyncio.ensure_future(cs.search(album, artist)) for cs in cover_sources]
    await asyncio.gather(*search_futs)
    results = []
    for fut in search_futs:
        results.extend(fut.result())
    results = await CoverSourceResult.preProcessForComparison(results, size, tol)
    results.sort(
        reverse=True,
        key=functools.cmp_to_key(
            functools.partial(
                CoverSourceResult.compare,
                target_size=size,
                size_tolerance_prct=tol,
            )
        ),
    )
    for cs in cover_sources:
        await cs.closeSession()
    if results:
        return results[0].urls[0]
    return ""

async def lookup_album_art(artist, album, ttl=300, fail_limit=3):
    """Lookup album art via SACAD but return the source URL."""
    hashed = hash_key(artist, album)
    key = f"cover:{hashed}"
    fail_key = f"fail:{hashed}"
    fails = None
    if rdb_available:
        try:
            fails = await rdb.get(fail_key)
        except Exception:
            fails = None
    if fails and int(fails) >= fail_limit:
        return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}

    cached = None
    if rdb_available:
        try:
            cached = await rdb.get(key)
        except Exception:
            cached = None
    if cached:
        await increment_cache_counter("cover", "hit")
        try:
            meta = json.loads(cached)
        except Exception:
            meta = None
        if meta and not str(meta.get("imageUrl", "")).startswith("data:"):
            return meta
        # Discard old base64 cache and refetch
        return json.loads(cached)

    await increment_cache_counter("cover", "miss")
    try:
        url = await sacad_search_url(artist, album)
        if url:
            meta = {"imageUrl": url, "itunesTrackUrl": "", "previewUrl": ""}
            if rdb_available:
                try:
                    await rdb.set(key, json.dumps(meta), ex=ttl)
                except Exception:
                    pass
            return meta
    except Exception as e:
        logging.error(f"[ERROR] SACAD lookup failed: {e}")
    if rdb_available:
        try:
            await rdb.incr(fail_key)
            await rdb.expire(fail_key, 86400)
        except Exception:
            pass
    return {"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}

async def to_spec_format(raw_tracks):
    central = timezone("America/Chicago")
    tasks = []
    for t in raw_tracks:
        artist = t.get("TPE1", "Family Radio")
        title = t.get("TIT2", "")
        album_csv = get_csv_album(artist, title)
        album = album_csv or t.get("TALB", title)
        if artist.strip().lower() == "family radio" or title.strip().lower() == "family radio":
            tasks.append(asyncio.sleep(0, result={"imageUrl": "", "itunesTrackUrl": "", "previewUrl": ""}))
        else:
            tasks.append(lookup_album_art(artist, album))
    metadatas = await asyncio.gather(*tasks)
    formatted = []
    for idx, (t, meta) in enumerate(zip(raw_tracks, metadatas)):
        artist = t.get("TPE1", "Family Radio")
        title = t.get("TIT2", "")
        album_csv = get_csv_album(artist, title)
        track_id = hash_key(artist, title)
        cache_key = f"track_start:{track_id}"
        if rdb_available:
            try:
                start_ts = await rdb.get(cache_key)
            except Exception:
                start_ts = None
        else:
            start_ts = None
        if start_ts is None:
            start_ts = str(datetime.now().timestamp())
            if rdb_available:
                try:
                    await rdb.set(cache_key, start_ts, ex=600)
                except Exception:
                    pass
        ts = datetime.fromtimestamp(float(start_ts), tz=central).isoformat()
        formatted.append({
            "id": str(uuid.uuid4()),
            "artist": artist,
            "title": title,
            "album": album_csv or t.get("TALB", ""),
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
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def get_feed_metrics(feed):
        if not rdb_available:
            periods = ["minute", "hour", "day", "week", "month", "year"]
            return {
                "feed": feed,
                "total": {p: 0 for p in periods},
                "unique": {p: 0 for p in periods},
            }
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

    if rdb_available:
        try:
            cache_feed_keys = await rdb.keys("feed:*")
            cache_cover_keys = await rdb.keys("cover:*")

            cache_hit_feed = await rdb.get("metrics:cache:feed:hit") or 0
            cache_miss_feed = await rdb.get("metrics:cache:feed:miss") or 0
            cache_hit_cover = await rdb.get("metrics:cache:cover:hit") or 0
            cache_miss_cover = await rdb.get("metrics:cache:cover:miss") or 0

            # Include last check times
            last_feed_check = await rdb.get('last_feed_check')
            last_feed_check_east = await rdb.get('last_feed_check:east')
            last_feed_check_west = await rdb.get('last_feed_check:west')
            last_feed_check_worship = await rdb.get('last_feed_check:worship')
            last_feed_check_fourth = await rdb.get('last_feed_check:fourth')
            last_feed_check_fifth = await rdb.get('last_feed_check:fifth')
        except Exception:
            cache_feed_keys = []
            cache_cover_keys = []
            cache_hit_feed = cache_miss_feed = 0
            cache_hit_cover = cache_miss_cover = 0
            last_feed_check = last_feed_check_east = None
            last_feed_check_west = last_feed_check_worship = None
            last_feed_check_fourth = last_feed_check_fifth = None
            logging.warning("Redis became unavailable during dashboard request")
    else:
        cache_feed_keys = []
        cache_cover_keys = []
        cache_hit_feed = cache_miss_feed = 0
        cache_hit_cover = cache_miss_cover = 0
        last_feed_check = last_feed_check_east = None
        last_feed_check_west = last_feed_check_worship = None
        last_feed_check_fourth = last_feed_check_fifth = None

    metrics_dict = {
        "timestamp": now,
        "feeds": metrics,
        "cache": {
            "feed_keys": len(cache_feed_keys),
            "cover_keys": len(cache_cover_keys),
            "hits": {
                "feed": int(cache_hit_feed),
                "cover": int(cache_hit_cover),
            },
            "misses": {
                "feed": int(cache_miss_feed),
                "cover": int(cache_miss_cover),
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

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "metrics": metrics_dict}
    )

@app.get("/admin/test-alert")
async def trigger_test_alert(credentials: HTTPBasicCredentials = Depends(security)):
    if not (
        secrets.compare_digest(credentials.username, USERNAME) and
        secrets.compare_digest(credentials.password, PASSWORD)
    ):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    pagerduty_key = PAGERDUTY_KEY
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
