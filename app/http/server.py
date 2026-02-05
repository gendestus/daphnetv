"""HTTP server for HLS streams and M3U."""
import logging
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


class HLSRequestHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves HLS streams, M3U, and EPG."""

    stream_dir = Path(os.getenv("STREAM_DIR", "/stream"))
    channels_callback: Callable[[], str] | None = None
    epg_callback: Callable[[], str] | None = None
    health_callback: Callable[[], bool] | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.stream_dir), **kwargs)

    def _send_content(self, content: str | bytes, content_type: str):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        """Handle GET requests for HLS manifest, segments, channels.m3u, epg.xml, health."""
        path = unquote(urlparse(self.path).path)
        path = path.lstrip("/")

        if path == "channels.m3u" and self.channels_callback:
            self._send_content(self.channels_callback(), "audio/x-mpegurl")
            return
        if path == "epg.xml" and self.epg_callback:
            self._send_content(self.epg_callback(), "application/xml")
            return
        if path == "health" and self.health_callback:
            ok = self.health_callback()
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK" if ok else b"Unhealthy")
            return

        # Serve from stream dir (path like kids-channel-1/channel.m3u8)
        return super().do_GET()

    def log_message(self, format, *args):
        logger.debug("%s - %s", self.address_string(), format % args)


def run_http_server(
    port: int = 8001,
    stream_dir: str | Path | None = None,
    channels_callback: Callable[[], str] | None = None,
    epg_callback: Callable[[], str] | None = None,
    health_callback: Callable[[], bool] | None = None,
) -> HTTPServer:
    """Run HTTP server for HLS streams."""
    HLSRequestHandler.stream_dir = Path(stream_dir or os.getenv("STREAM_DIR", "/stream"))
    HLSRequestHandler.channels_callback = channels_callback
    HLSRequestHandler.epg_callback = epg_callback
    HLSRequestHandler.health_callback = health_callback

    server = HTTPServer(("0.0.0.0", port), HLSRequestHandler)
    logger.info("HTTP server listening on port %d", port)
    return server
