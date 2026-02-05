# DaphneTV Development Checklist

**Status:** All phases implemented. Use this checklist for verification and future enhancements.

## Phase 0: Project Setup ✅

- [x] 0.1 Create project root and layout
- [x] 0.2 requirements.txt (requests, pyyaml, python-dotenv, schedule)
- [x] 0.3 .env.example
- [x] 0.4 .gitignore
- [x] 0.5 config/config.yaml
- [x] 0.6 Dockerfile
- [x] 0.7 docker-compose.yml
- [ ] 0.8 Verify: `docker-compose build` (requires Docker)

## Phase 1: Config & Jellyfin ✅

- [x] 1.1 app/config/loader.py
- [x] 1.2 Config schema validation
- [x] 1.3 app/jellyfin/client.py
- [x] 1.4 Jellyfin API integration
- [x] 1.5 Optional metadata cache (not implemented; add if needed)
- [ ] 1.6 Verify: Fetch items from Jellyfin (requires running Jellyfin)

## Phase 2: Schedule Generator ✅

- [x] 2.1 app/scheduler/generator.py
- [x] 2.2 generate_daily_schedule()
- [x] 2.3 Time slot → category mapping
- [x] 2.4 Content selection (random)
- [x] 2.5 Start/end time calculation
- [x] 2.6 Save schedule JSON
- [ ] 2.7 Verify: Schedule JSON covers 24h (run with Jellyfin)

## Phase 3: Ad Insertion ✅

- [x] 3.1 app/scheduler/ad_insertion.py
- [x] 3.2 Time-based ad breaks
- [x] 3.3 Round-robin rotation
- [x] 3.4 ads_per_break from config
- [x] 3.5 Scan ad directory
- [x] 3.6 Integration with schedule generator
- [ ] 3.7 Verify: Schedule has ad_block entries

## Phase 4: Concat Playlist ✅

- [x] 4.1 app/scheduler/playlist.py
- [x] 4.2 Schedule → FFmpeg concat format
- [x] 4.3 Path escaping
- [x] 4.4 File existence validation
- [x] 4.5 Write playlist file
- [ ] 4.6 Verify: `ffmpeg -f concat -i playlist.txt -c copy -t 60 test.mp4`

## Phase 5: FFmpeg Manager ✅

- [x] 5.1 app/stream/ffmpeg_manager.py
- [x] 5.2 FFmpeg subprocess
- [x] 5.3 HLS output flags
- [x] 5.4 Segment output paths
- [x] 5.5 Health check
- [x] 5.6 Restart on exit
- [ ] 5.7 Verify: HLS manifest updates

## Phase 6: HTTP Serving ✅

- [x] 6.1 app/http/server.py
- [x] 6.2 Serve HLS manifest + segments
- [x] 6.3 /channels.m3u
- [x] 6.4 CORS (add if needed for web clients)
- [ ] 6.5 Verify: VLC plays stream

## Phase 7: Main Orchestration ✅

- [x] 7.1 app/main.py entry point
- [x] 7.2 Config load, channel loop
- [x] 7.3 Schedule → playlist → FFmpeg pipeline
- [x] 7.4 HTTP server start
- [x] 7.5 SIGTERM handling
- [ ] 7.6 Verify: docker-compose up, stream in Jellyfin Live TV

## Phase 8: Daily Regeneration ✅

- [x] 8.1 schedule.every().day.at("00:00")
- [x] 8.2 Regenerate next day schedule
- [x] 8.3 FFmpeg restart with new playlist
- [x] 8.4 State persistence (schedule JSON)
- [ ] 8.5 Verify: Simulate midnight or wait 24h

## Phase 9: EPG & M3U ✅

- [x] 9.1 app/epg/xmltv.py
- [x] 9.2 XMLTV format
- [x] 9.3 /epg.xml endpoint
- [x] 9.4 M3U with tvg-id
- [ ] 9.5 Verify: Jellyfin shows EPG

## Phase 10: Multi-Channel ✅

- [x] 10.1 Config supports multiple channels
- [x] 10.2 One FFmpeg per channel
- [x] 10.3 Separate playlists per channel
- [x] 10.4 M3U includes all channels
- [ ] 10.5 Verify: All channels playable

## Phase 11: Reliability ✅

- [x] 11.1 Structured logging
- [x] 11.2 Error logging
- [x] 11.3 /health endpoint
- [x] 11.4 README documentation
- [x] 11.5 Error handling in key paths

## Verification Commands

```bash
# Build
docker-compose build

# Run
docker-compose up -d

# Check stream
curl -s http://localhost:8001/kids-channel-1/channel.m3u8 | head -20

# Check M3U
curl -s http://localhost:8001/channels.m3u

# Check EPG
curl -s http://localhost:8001/epg.xml | head -30

# Check health
curl -s http://localhost:8001/health

# Logs
docker-compose logs -f
```
