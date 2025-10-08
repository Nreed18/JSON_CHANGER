# Family Radio JSON Metadata Feed

## Overview
This is a FastAPI-based application that exposes JSON metadata feeds for Family Radio stations. It fetches metadata from upstream CDN sources, enriches it with album artwork from multiple sources (iTunes API, SACAD, manual overrides), and provides a clean admin dashboard for monitoring.

## Recent Changes (October 2025)
- ✅ Configured for Replit environment with port 5000
- ✅ Enhanced album art functionality with fallback images
- ✅ Redesigned admin dashboard with modern UI
- ✅ Redis integration for caching and metrics (optional)
- ✅ Deployment configuration set up

## Project Architecture

### Main Components
- **main.py** - FastAPI application with all endpoints and business logic
- **templates/admin_dashboard.html** - Modern admin dashboard UI
- **album_lookup.csv** - Manual album mappings (1929 entries loaded)
- **latency_monitor.py** - External monitoring script for feed health

### Key Features
1. **Multi-Feed Support** - East, West, Worship, Fourth, and Fifth feeds
2. **Album Art Enrichment** - Multiple sources with fallback
   - Manual podcast overrides (50+ shows)
   - iTunes Search API
   - CSV album lookup
   - SACAD (multiple cover art sources)
   - Fallback to Family Radio logo
3. **Admin Dashboard** - Real-time metrics and feed health monitoring
4. **Caching** - Redis-based caching for feeds and album art
5. **Metrics** - Track unique visitors and request counts

## Technology Stack
- **Backend**: FastAPI + Uvicorn
- **Database**: Redis (optional, for caching/metrics)
- **Album Art**: SACAD, iTunes API
- **Frontend**: Jinja2 templates with custom CSS

## Environment Variables
- `ADMIN_USER` - Dashboard username (default: admin)
- `ADMIN_PASSWORD` - Dashboard password (default: familyradio2025)
- `PD_ROUTING_KEY` - PagerDuty routing key for alerts
- `REDIS_HOST` - Redis hostname (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `ALBUM_LOOKUP_CSV` - Path to album CSV (default: album_lookup.csv)

## Endpoints
- `GET /` - Homepage with feed links
- `GET /east-feed.json` - East feed metadata
- `GET /west-feed.json` - West feed metadata
- `GET /worship-feed.json` - Worship feed metadata
- `GET /fourth-feed.json` - Fourth feed metadata
- `GET /fifth-feed.json` - Fifth feed metadata
- `GET /admin/dashboard` - Admin dashboard (requires auth)
- `GET /admin/test-alert` - Send test PagerDuty alert

## Development Notes
- The app works without Redis but caching/metrics will be disabled
- Album art lookup tries multiple sources in order: manual overrides → iTunes → SACAD → fallback
- The admin dashboard shows real-time feed status and cache performance
- Fourth and Fifth feed URLs need to be configured when available

## Deployment
The application is configured for VM deployment (always-on) with 2 workers for better performance.
