# DaphneTV

Jellyfin 24/7 TV Channel System — creates linear TV channels from your Jellyfin media library with integrated advertisements.

## Overview

- **Scheduler**: Fetches content from Jellyfin API, generates 24-hour schedules, inserts ads
- **FFmpeg**: Streams content as continuous HLS
- **HTTP Server**: Serves HLS manifest, segments, M3U playlist, and EPG

## Quick Start

1. Copy `.env.example` to `.env` and set your Jellyfin API key
2. Update `config/config.yaml` with your channel definitions
3. Update `docker-compose.yml` volume paths for media and ads
4. Run: `docker-compose up -d`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JELLYFIN_URL` | Jellyfin server URL | `http://jellyfin:8096` |
| `JELLYFIN_API_KEY` | Jellyfin API key | (required) |
| `CHANNEL_ID` | Run single channel only | (all channels) |
| `TZ` | Timezone for scheduling | `America/New_York` |
| `CONFIG_DIR` | Config directory path | `/config` |
| `STREAM_DIR` | HLS output directory | `/stream` |
| `M3U_BASE_URL` | Base URL for M3U stream links | `http://localhost:8001` |

### config.yaml

- **channels**: List of channel definitions with id, name, port, schedule blocks, ad_rotation
- **jellyfin**: url, api_key
- **ads**: directory path, supported formats (.mp4, .mkv)

Schedule blocks use `time` (HH:MM-HH:MM), `category` (Jellyfin genre/tag), and `ad_frequency` (seconds).

## Endpoints

- `GET /channels.m3u` — M3U playlist for Jellyfin Live TV
- `GET /epg.xml` — XMLTV EPG
- `GET /health` — Health check (200 if streams OK)
- `GET /{channel_id}/channel.m3u8` — HLS manifest per channel
- `GET /{channel_id}/segment_*.ts` — HLS segments

## Jellyfin Setup

1. Dashboard → Live TV → Add Tuner
2. Select M3U Tuner
3. URL: `http://your-server:8001/channels.m3u`
4. (Optional) EPG URL: `http://your-server:8001/epg.xml`

## Development

```bash
pip install -r requirements.txt
python -m app.main
```

## Troubleshooting

- **No schedule generated**: Check Jellyfin API key and that library has content with matching genres/tags
- **Stream won't start**: Verify media and ad file paths exist in container
- **Playback stuttering**: Try increasing `-hls_time` in ffmpeg_manager.py
