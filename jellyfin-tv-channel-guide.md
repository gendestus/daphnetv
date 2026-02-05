# Jellyfin 24/7 TV Channel System

## Overview

A Docker-based system that creates linear TV channels from your Jellyfin media library with integrated advertisements, providing an authentic "always-on" television experience.

## Core Concept

The system uses FFmpeg to create continuous HLS (HTTP Live Streaming) streams from scheduled playlists that combine your media with ads. The stream runs 24/7, allowing viewers to tune in at any time and find content already playing, just like traditional television.

---

## Architecture

### Single Container Design

**Container Components:**
1. **Scheduler Service** (Python/Node.js)
2. **FFmpeg Streaming Engine**
3. **HTTP Server** (for HLS segments)
4. **Configuration Manager**

**Container Mounts:**
- Jellyfin media directory (read-only)
- Persistent config/state volume
- Ad media directory

---

## System Components

### 1. Scheduler Service

**Responsibilities:**
- Query Jellyfin API for available content
- Generate daily programming schedules
- Insert ads at appropriate intervals
- Create FFmpeg concat playlists
- Manage FFmpeg process lifecycle
- Regenerate schedules automatically

**Key Functions:**
```python
# Pseudocode structure
class ChannelScheduler:
    def generate_daily_schedule():
        # Create 24-hour programming block
        # Map time slots to content types
        # Select specific episodes/movies from Jellyfin
        
    def insert_ads(schedule):
        # Add ads at intervals (every 15min, between shows, etc.)
        # Rotate through ad inventory
        
    def create_concat_playlist(schedule):
        # Generate FFmpeg concat file format
        # Map to actual file paths
        
    def start_stream():
        # Launch FFmpeg with generated playlist
        # Monitor process health
```

**Schedule Data Structure:**
```json
{
  "date": "2025-02-05",
  "channel_id": "kids-channel-1",
  "blocks": [
    {
      "start_time": "07:00:00",
      "end_time": "07:23:00",
      "type": "show",
      "title": "Cartoon Episode 1",
      "jellyfin_id": "abc123",
      "file_path": "/media/shows/cartoon/s01e01.mp4"
    },
    {
      "start_time": "07:23:00",
      "end_time": "07:26:00",
      "type": "ad_block",
      "ads": [
        {"title": "Ad 1", "file_path": "/ads/ad001.mp4"},
        {"title": "Ad 2", "file_path": "/ads/ad002.mp4"}
      ]
    }
  ]
}
```

### 2. FFmpeg Streaming Engine

**Purpose:** Convert scheduled playlists into continuous HLS streams

**FFmpeg Command Structure:**
```bash
ffmpeg -re \
  -f concat -safe 0 -i /config/playlist.txt \
  -c:v copy -c:a copy \
  -f hls \
  -hls_time 10 \
  -hls_list_size 6 \
  -hls_flags delete_segments+append_list \
  -hls_segment_filename /stream/segment_%03d.ts \
  /stream/channel.m3u8
```

**Parameter Breakdown:**
- `-re` - Read input at native frame rate (real-time simulation)
- `-f concat -safe 0` - Concatenate multiple input files
- `-i /config/playlist.txt` - Input playlist file
- `-c:v copy -c:a copy` - Stream copy (no re-encoding = fast & efficient)
- `-f hls` - Output HTTP Live Streaming format
- `-hls_time 10` - 10-second segment duration
- `-hls_list_size 6` - Keep last 6 segments in playlist
- `-hls_flags delete_segments+append_list` - Cleanup old segments, append new ones

**Concat Playlist Format** (`playlist.txt`):
```
file '/media/shows/cartoon/s01e01.mp4'
file '/ads/ad001.mp4'
file '/ads/ad002.mp4'
file '/media/shows/cartoon/s01e02.mp4'
file '/ads/ad003.mp4'
```

### 3. HTTP Server

**Purpose:** Serve HLS manifest and segments to clients

**Options:**
- **Simple:** Python `http.server` module
- **Production:** Nginx (lightweight, efficient)
- **Integrated:** Serve directly from your scheduler app (Flask/Express)

**What it serves:**
- `/channel.m3u8` - HLS manifest (playlist of segments)
- `/segment_*.ts` - Video segments (10-second chunks)

### 4. Configuration Manager

**Purpose:** Store channel definitions, scheduling rules, ad rotation policies

**Configuration File Example** (`config.yaml`):
```yaml
channels:
  - id: kids-channel-1
    name: "Saturday Morning Cartoons"
    port: 8001
    schedule:
      - time: "07:00-09:00"
        category: "cartoons"
        ad_frequency: 900  # seconds (15 min)
      - time: "09:00-12:00"
        category: "educational"
        ad_frequency: 1200  # seconds (20 min)
      - time: "12:00-14:00"
        category: "movies"
        ad_frequency: 1800  # seconds (30 min)
    
    ad_rotation:
      strategy: "round-robin"  # or "weighted", "random"
      ads_per_break: 2

jellyfin:
  url: "http://jellyfin:8096"
  api_key: "your-api-key"
  
ads:
  directory: "/ads"
  formats: [".mp4", ".mkv"]
```

---

## Implementation Strategy

### Phase 1: Core Scheduling Engine

1. **Jellyfin API Integration**
   - Fetch library items by category/tags
   - Get file paths for media items
   - Cache metadata locally

2. **Schedule Generator**
   - Create time-based programming blocks
   - Select content based on rules (random, sequential, weighted)
   - Calculate exact start/end times for each item

3. **Ad Insertion Logic**
   - Define ad break triggers (time-based, content-based)
   - Rotate through ad inventory
   - Ensure ads fit within time constraints

### Phase 2: FFmpeg Integration

1. **Concat Playlist Generation**
   - Convert schedule to FFmpeg concat format
   - Validate all file paths exist
   - Handle file path escaping

2. **Stream Process Management**
   - Launch FFmpeg as subprocess
   - Monitor process health (restart on failure)
   - Handle graceful restarts for schedule updates

3. **HLS Output Configuration**
   - Configure segment duration for smooth playback
   - Manage disk space (auto-delete old segments)
   - Optimize for network conditions

### Phase 3: HTTP Serving

1. **Stream Endpoint Setup**
   - Serve HLS manifest at predictable URL
   - Handle CORS if needed for web clients
   - Add basic authentication (optional)

2. **M3U Playlist Generation**
   - Create m3u file pointing to your HLS stream
   - Add EPG metadata (tvg-id, tvg-logo, etc.)

### Phase 4: Automation & Reliability

1. **Daily Schedule Regeneration**
   - Cron job or scheduled task at midnight
   - Generate next day's schedule
   - Seamless transition between schedules

2. **Health Monitoring**
   - Check FFmpeg process status
   - Verify stream availability
   - Log errors and restart on failure

3. **State Persistence**
   - Save current schedule position
   - Track ad rotation state
   - Resume gracefully after container restart

---

## Docker Implementation

### Dockerfile Structure

```dockerfile
FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/

# Create directories
RUN mkdir -p /config /stream /ads

WORKDIR /app

# Expose HTTP port for HLS stream
EXPOSE 8001

# Run scheduler service
CMD ["python", "scheduler.py"]
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  tv-channel:
    build: .
    container_name: jellyfin-tv-channel
    restart: unless-stopped
    
    volumes:
      # Jellyfin media library (read-only)
      - /path/to/jellyfin/media:/media:ro
      
      # Your ads directory
      - /path/to/ads:/ads:ro
      
      # Persistent config and state
      - ./config:/config
      
      # Stream output (ephemeral, could use tmpfs)
      - ./stream:/stream
    
    environment:
      - JELLYFIN_URL=http://jellyfin:8096
      - JELLYFIN_API_KEY=your-api-key-here
      - CHANNEL_ID=kids-channel-1
      - TZ=America/New_York
    
    ports:
      - "8001:8001"
    
    networks:
      - jellyfin-network

networks:
  jellyfin-network:
    external: true
```

---

## M3U Integration

### Generated M3U File

Your scheduler generates an m3u file that Jellyfin's Live TV can use:

**File:** `channels.m3u`
```m3u
#EXTM3U
#EXTINF:-1 tvg-id="kids-channel-1" tvg-logo="http://yourserver/logos/kids.png" tvg-name="Kids Channel",Kids Channel
http://yourserver:8001/channel.m3u8
```

### Jellyfin Configuration

1. Go to **Dashboard → Live TV**
2. Add **Tuner**: Select "M3U Tuner"
3. Point to your m3u file: `http://yourserver:8001/channels.m3u`
4. (Optional) Add EPG source for program guide

---

## Advanced Features

### EPG (Electronic Program Guide)

Generate XMLTV format guide data so Jellyfin shows what's currently playing:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="kids-channel-1">
    <display-name>Kids Channel</display-name>
  </channel>
  
  <programme start="20250205070000 +0000" stop="20250205072300 +0000" channel="kids-channel-1">
    <title>Cartoon Show - Episode 1</title>
    <desc>Description here</desc>
    <category>Cartoons</category>
  </programme>
</tv>
```

### Multiple Channels

Scale to multiple channels by:
- Running multiple FFmpeg processes (one per channel)
- Different ports for each channel
- Separate schedules and configurations
- Single m3u with multiple channel entries

### Ad Analytics

Track ad playback:
- Log when each ad plays
- Count impressions
- Rotate ads based on play count
- A/B test different ad strategies

### Smart Scheduling

- **Time-aware content**: Educational shows in morning, movies in afternoon
- **Age-appropriate filtering**: Different channels for different age groups
- **Seasonal programming**: Holiday specials during appropriate times
- **Binge blocks**: Marathon sessions of single shows

---

## Troubleshooting

### Common Issues

**Stream won't start:**
- Check FFmpeg logs for errors
- Verify all file paths in concat playlist exist
- Ensure media files are readable by container user

**Playback stuttering:**
- Increase HLS segment size (`-hls_time 10` → `20`)
- Check disk I/O (use SSD for stream output)
- Verify network bandwidth

**Schedule gaps:**
- Ensure schedule generator covers full 24 hours
- Add filler content for gaps
- Log warnings when schedule is incomplete

**Container crashes:**
- Check memory usage (FFmpeg can be hungry)
- Monitor CPU usage during transcoding
- Add restart policy to docker-compose

### Debugging Tips

```bash
# Watch FFmpeg output in real-time
docker logs -f jellyfin-tv-channel

# Check current stream status
curl http://localhost:8001/channel.m3u8

# Validate concat playlist
cat /path/to/config/playlist.txt

# Test FFmpeg command manually
docker exec -it jellyfin-tv-channel bash
ffmpeg -f concat -i /config/playlist.txt -c copy -t 60 test.mp4
```

---

## Performance Optimization

### Stream Copy vs Transcoding

**Current approach** (stream copy):
- ✅ Fast, minimal CPU usage
- ✅ No quality loss
- ❌ Requires compatible formats across all media

**If you need transcoding**:
```bash
# Replace: -c:v copy -c:a copy
# With:
-c:v libx264 -preset veryfast -c:a aac
```

### Disk Space Management

HLS segments accumulate quickly. Options:
- Use `delete_segments` flag (already included)
- Mount `/stream` as tmpfs (RAM disk)
- Run cleanup cron job

### Memory Usage

Typical footprint:
- Python scheduler: 50-100MB
- FFmpeg: 100-300MB (stream copy) or 500MB-2GB (transcoding)
- HTTP server: 10-50MB

---

## Future Enhancements

- **Web UI**: Dashboard to manage schedules, view current programming
- **API**: REST API for dynamic schedule updates
- **Multi-container**: Separate scheduler from streaming for better resource management
- **Cloud storage**: Support for media on S3/cloud storage
- **Dynamic ads**: Serve different ads based on time of day, content type
- **Viewer analytics**: Track what people watch, when they tune in
- **Picture-in-picture**: Multiple channels composited into one stream
- **Live content**: Inject live streams alongside recorded content

---

## Resources

- [FFmpeg HLS Documentation](https://ffmpeg.org/ffmpeg-formats.html#hls-2)
- [M3U Format Specification](https://en.wikipedia.org/wiki/M3U)
- [XMLTV EPG Format](http://wiki.xmltv.org/index.php/XMLTVFormat)
- [Jellyfin API Documentation](https://api.jellyfin.org/)
- [dizqueTV Project](https://github.com/vexorian/dizquetv) (similar implementation)

---

## Quick Start Commands

```bash
# Build container
docker-compose build

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Restart after config change
docker-compose restart

# Stop service
docker-compose down
```

---

**Last Updated:** 2025-02-05
**Version:** 1.0
