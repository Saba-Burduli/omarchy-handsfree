"""JSON-lines control socket between `handsfree-ctl` and the daemon."""

from __future__ import annotations

import json
import logging
import os
import socket
import socketserver
import threading
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class _RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline()
        try:
            response = self.server.app_handler(json.loads(line))  # type: ignore[attr-defined]
        except Exception as exc:  # report, never kill the server thread
            log.exception("control request failed")
            response = {"ok": False, "error": str(exc)}
        self.wfile.write(json.dumps(response).encode() + b"\n")


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class ControlServer:
    def __init__(self, path: Path, handler: Handler):
        self.path = path
        self.handler = handler
        self._server: _Server | None = None

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.exists():
            self.path.unlink()
        server = _Server(str(self.path), _RequestHandler)
        server.app_handler = self.handler  # type: ignore[attr-defined]
        os.chmod(self.path, 0o600)
        threading.Thread(target=server.serve_forever, name="ipc", daemon=True).start()
        self._server = server

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self.path.unlink(missing_ok=True)


def request(path: Path, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall(json.dumps(payload).encode() + b"\n")
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data)
