# JSON Changer

This project exposes JSON metadata feeds via a FastAPI app and provides a simple admin dashboard for monitoring feed health.

## Installation

### Prerequisites

- Python 3.x
- Redis server
- Git

### Quick Start

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv redis-server
sudo systemctl enable --now redis-server

# Clone and install
git clone <REPO_URL>
cd JSON_CHANGER

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn main:app
```

**Note:** Remember to activate the virtual environment (`source venv/bin/activate`) each time you work with the project.

The app will start on `http://localhost:8000`. Add `--reload` flag for development.

### Configuration

Environment variables (all optional with defaults):

- `PD_ROUTING_KEY` – PagerDuty routing key for alerts from `latency_monitor.py`
- `ADMIN_USER` and `ADMIN_PASSWORD` – Dashboard credentials (default: `admin`/`familyradio2025`)
- `REDIS_HOST` and `REDIS_PORT` – Redis connection (default: `localhost:6379`)
- `ALBUM_LOOKUP_CSV` – Path to CSV for album art lookup (default: `album_lookup.csv`)

### Album Art Lookup (Optional)

Improve album art accuracy by providing a CSV file with track-to-album mappings:

```csv
title,artist,album
Awesome Song,Example Artist,Greatest Hits
```

Place as `album_lookup.csv` in the project root or set `ALBUM_LOOKUP_CSV` to another path. The app uses [SACAD](https://github.com/desbma/sacad) for album art searches.

## Admin Dashboard

Navigate to `/admin/dashboard` to view feed metrics, cache statistics, and the overall health status of each feed. Authentication is handled by HTTP basic auth using the credentials defined in `main.py` (`USERNAME` and `PASSWORD`).

## Configuring Feeds

Feed URLs are defined as constants (`SOURCE_EAST`, `SOURCE_WEST`, `SOURCE_THIRD`, etc.) in `main.py`. To add a new feed, create an additional constant and extend the endpoints accordingly. Update the `FEEDS` dictionary in `latency_monitor.py` so the latency monitor checks the new feed as well.

## Cloudflared Tunnel Setup (Optional)

Expose the FastAPI service through a secure Cloudflare Tunnel:

```bash
# Install cloudflared
sudo apt install cloudflared

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create <TUNNEL_NAME>

# Copy and configure
sudo cp cloudflared/config.yml /etc/cloudflared/config.yml
# Edit /etc/cloudflared/config.yml with your tunnel ID, credentials path, and hostname

# Set up systemd service
sudo useradd -r -g nogroup cloudflared || true
sudo cp cloudflared/cloudflared.service /etc/systemd/system/cloudflared.service
sudo systemctl enable --now cloudflared
```

The credentials file is at `~/.cloudflared/<TUNNEL_ID>.json` - reference this path in `/etc/cloudflared/config.yml`.
