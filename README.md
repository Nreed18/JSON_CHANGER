# JSON Changer

This project exposes JSON metadata feeds via a FastAPI app and provides a simple admin dashboard for monitoring feed health.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

This will install [SACAD](https://github.com/desbma/sacad) for album art search.

2. Set environment variables (adjust as needed):

- `PD_ROUTING_KEY` – PagerDuty routing key used by `latency_monitor.py` when it sends alerts.
- `ADMIN_USER` and `ADMIN_PASSWORD` – credentials for accessing the dashboard (default: `admin`/`familyradio2025`).
- `REDIS_HOST` and `REDIS_PORT` – connection info for your Redis instance (defaults to `localhost` and `6379`).
- `ALBUM_LOOKUP_CSV` – optional path to a CSV file mapping track `title` and `artist` to an `album` name used for SACAD album art searches. Defaults to `album_lookup.csv` in the project root.

3. Run the application:

```bash
uvicorn main:app
```

The app will start on port 8000 by default. You can add the `--reload` flag during development.

## Album Lookup CSV

To improve album art accuracy you can provide a CSV file with `title`, `artist`, and `album` columns. When a matching row is found, the album name from the CSV is used for SACAD searches.

1. Create a CSV file named `album_lookup.csv` in the project root (or set the `ALBUM_LOOKUP_CSV` environment variable to another location).
2. Each row should contain `title`, `artist`, and `album` headers, for example:

   ```csv
   title,artist,album
   Awesome Song,Example Artist,Greatest Hits
   ```

3. Restart the application so the file is loaded on startup.

## Ubuntu Quickstart

Follow these steps on a clean Ubuntu install to get the application running:

1. Install system packages and start Redis:

```bash
sudo apt update
sudo apt install -y python3 python3-pip git redis-server
sudo systemctl enable --now redis-server
```

2. Clone this repository and install the Python dependencies:

```bash
git clone <REPO_URL>
cd JSON_CHANGER
pip3 install -r requirements.txt
```

3. Set the environment variables listed below (at minimum `PD_ROUTING_KEY`) and start the FastAPI server:

```bash
uvicorn main:app
```

You can also set up the Cloudflare tunnel as described in the next section to expose the service publicly.

## Admin Dashboard

Navigate to `/admin/dashboard` to view feed metrics, cache statistics, and the overall health status of each feed. Authentication is handled by HTTP basic auth using the credentials defined in `main.py` (`USERNAME` and `PASSWORD`).

## Configuring Feeds

Feed URLs are defined as constants (`SOURCE_EAST`, `SOURCE_WEST`, `SOURCE_THIRD`, etc.) in `main.py`. To add a new feed, create an additional constant and extend the endpoints accordingly. Update the `FEEDS` dictionary in `latency_monitor.py` so the latency monitor checks the new feed as well.

## Cloudflared Tunnel Setup

To expose the FastAPI service through a secure Cloudflare Tunnel, install `cloudflared` and configure it as a systemd service. These steps work on any Ubuntu-based distribution.

1. Install the package:

```bash
sudo apt update
sudo apt install cloudflared
```

2. Authenticate and create a tunnel (or reuse an existing one):
```bash
cloudflared tunnel login
# Create a new tunnel
cloudflared tunnel create <TUNNEL_NAME>
# Or view existing tunnels and download credentials for one
cloudflared tunnel list
cloudflared tunnel token <TUNNEL_NAME>
```

The `token` command downloads the credentials file for the selected tunnel to
`~/.cloudflared/<TUNNEL_ID>.json`. Point the `credentials-file` option in
`/etc/cloudflared/config.yml` to this path.



3. Copy `cloudflared/config.yml` from this repository to `/etc/cloudflared/config.yml` and update it with your tunnel ID, credentials file path and hostname.

4. Install the systemd service:

```bash
sudo useradd -r -g nogroup cloudflared || true
sudo cp cloudflared/cloudflared.service /etc/systemd/system/cloudflared.service
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

After the service starts, the application will be reachable through the hostname specified in your Cloudflare configuration.
