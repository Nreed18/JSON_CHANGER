# JSON Changer

This project exposes JSON metadata feeds via a FastAPI app and provides a simple admin dashboard for monitoring feed health.

## Setup

1. Install dependencies:

```bash
pip install -r project/requirements.txt
```

2. Set environment variables:

- `PD_ROUTING_KEY` – PagerDuty routing key used by `latency_monitor.py` when it sends alerts.

3. Run the application:

```bash
uvicorn project.main:app
```

The app will start on port 8000 by default. You can add the `--reload` flag during development.

## Admin Dashboard

Navigate to `/admin/dashboard` to view feed metrics, cache statistics, and the overall health status of each feed. Authentication is handled by HTTP basic auth using the credentials defined in `project/main.py` (`USERNAME` and `PASSWORD`).

## Configuring Feeds

Feed URLs are defined as constants (`SOURCE_EAST`, `SOURCE_WEST`, `SOURCE_THIRD`, etc.) in `project/main.py`. To add a new feed, create an additional constant and extend the endpoints accordingly. Update the `FEEDS` dictionary in `project/latency_monitor.py` so the latency monitor checks the new feed as well.
