FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project (app package must be at /app/app/)
COPY . /app/

# Create directories
RUN mkdir -p /config /stream /ads /config/playlists /config/schedules

WORKDIR /app

# Expose HTTP port for HLS stream
EXPOSE 8001

# Run as module so app package is on path
CMD ["python", "-m", "app.main"]
