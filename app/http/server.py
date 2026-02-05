"""HTTP server for HLS streams and M3U."""
import io
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

    def _norm_path(self) -> str:
        """Normalize request path for matching."""
        return unquote(urlparse(self.path).path).strip("/").lower() or ""

    def _send_content(self, content: str | bytes, content_type: str):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_index(self):
        """Serve index page with links to channels.m3u, epg.xml, streams."""
        streams = []
        stream_path = Path(os.getenv("STREAM_DIR", "/stream"))
        if stream_path.exists():
            for d in stream_path.iterdir():
                if d.is_dir():
                    manifest = d / "channel.m3u8"
                    if manifest.exists():
                        streams.append(f'<li><a href="/{d.name}/channel.m3u8">{d.name}</a></li>')
        streams_html = "\n".join(streams) if streams else "<li>No streams</li>"
        html = f"""<!DOCTYPE html>
<html><head><title>DaphneTV</title></head><body>
<h1>DaphneTV</h1>
<ul>
<li><a href="/channels.m3u">channels.m3u</a> - M3U playlist for Jellyfin Live TV</li>
<li><a href="/epg.xml">epg.xml</a> - XMLTV EPG</li>
<li><a href="/health">health</a> - Health check</li>
</ul>
<h2>Streams</h2>
<ul>{streams_html}</ul>
</body></html>"""
        self._send_content(html, "text/html")

    def send_head(self):
        """Intercept virtual paths before file lookup; parent returns 404 for non-existent files."""
        path = self._norm_path()

        if path == "":
            self._send_index()
            return None
        if path == "channels.m3u" and self.channels_callback:
            try:
                content = self.channels_callback()
                data = content.encode("utf-8")
            except Exception as e:
                logger.exception("channels_callback failed: %s", e)
                self.send_error(500)
                return None
            self.send_response(200)
            self.send_header("Content-Type", "audio/x-mpegurl")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return io.BytesIO(data)
        if path == "epg.xml" and self.epg_callback:
            try:
                content = self.epg_callback()
                data = content.encode("utf-8")
            except Exception as e:
                logger.exception("epg_callback failed: %s", e)
                self.send_error(500)
                return None
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return io.BytesIO(data)
        if path == "health" and self.health_callback:
            ok = self.health_callback()
            self.send_response(200 if ok else 503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK" if ok else b"Unhealthy")
            return None

        return super().send_head()

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
