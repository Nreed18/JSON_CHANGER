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
