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

### Running as a Systemd Service (Production)

To run the app automatically on boot and manage it as a system service:

```bash
# Move the project to a standard location
sudo mv JSON_CHANGER /opt/
cd /opt/JSON_CHANGER

# Set up virtual environment with proper permissions
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo chown -R www-data:www-data /opt/JSON_CHANGER

# Install and start the service
sudo cp json-changer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable json-changer
sudo systemctl start json-changer

# Check status
sudo systemctl status json-changer
```

**Service management commands:**
- `sudo systemctl start json-changer` - Start the service
- `sudo systemctl stop json-changer` - Stop the service
- `sudo systemctl restart json-changer` - Restart the service
- `sudo systemctl status json-changer` - Check service status
- `sudo journalctl -u json-changer -f` - View live logs

**To set environment variables for the service:**

```bash
sudo mkdir -p /etc/json-changer
sudo nano /etc/json-changer/environment
```

Add your variables in KEY=VALUE format:
```
PD_ROUTING_KEY=your_key_here
ADMIN_USER=admin
ADMIN_PASSWORD=your_password
REDIS_HOST=localhost
REDIS_PORT=6379
```

Then restart: `sudo systemctl restart json-changer`

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
