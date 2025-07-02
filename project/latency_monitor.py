import requests
import time
import os

PAGERDUTY_KEY = os.getenv("PD_ROUTING_KEY")
ALERT_THRESHOLD = 10  # seconds

FEEDS = {
    "east": "https://metadata.fr-infra.com/east-feed.json",
    "west": "https://metadata.fr-infra.com/west-feed.json",
    "worship": "https://metadata.fr-infra.com/worship-feed.json"
}

def send_pagerduty_alert(feed_name, latency):
    summary = f"🚨 {feed_name.capitalize()} metadata feed response time error ({latency:.2f}s)"
    payload = {
        "routing_key": be2800efd3ac410fc05d30cea86764f9,
        "event_action": "trigger",
        "payload": {
            "summary": summary,
            "severity": "warning",
            "source": f"{feed_name}-feed",
            "component": "metadata-api",
            "custom_details": {
                "latency": f"{latency:.2f}s",
                "feed_url": FEEDS[feed_name]
            }
        },
        "dedup_key": f"latency-{feed_name}"
    }
    try:
        r = requests.post("https://events.pagerduty.com/v2/enqueue", json=payload, timeout=5)
        print(f"[{feed_name}] Alert sent: {r.status_code}")
    except Exception as e:
        print(f"[{feed_name}] Alert FAILED:", e)

def check_feed(feed_name, url):
    try:
        start = time.time()
        r = requests.get(url, timeout=15)
        latency = time.time() - start
        print(f"[{feed_name}] Checked: {latency:.2f}s")

        if latency >= ALERT_THRESHOLD:
            send_pagerduty_alert(feed_name, latency)
    except Exception as e:
        print(f"[{feed_name}] Error: {e}")
        send_pagerduty_alert(feed_name, 60)

def main():
    for name, url in FEEDS.items():
        check_feed(name, url)

if __name__ == "__main__":
    main()
