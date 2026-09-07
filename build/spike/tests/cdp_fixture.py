"""cdp_fixture.py — a loopback WebSocket/CDP echo server for the unit tests.

Stdlib only (threading + socket), exactly like the client it exercises. It
implements the RFC 6455 handshake, unmasks client frames, and answers a CDP
shaped request with `{"id": <id>, "result": {"echo": "<method>"}}`.

It deliberately does NOT implement compression or fragmentation on the send
side, so a client that silently depends on them fails the test rather than
passing by luck.
"""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import socketserver
import struct
import threading

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        sock = self.request
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        key = ""
        for line in head.decode(errors="replace").split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        sock.sendall(
            ("HTTP/1.1 101 Switching Protocols\r\n"
             "Upgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             f"Sec-WebSocket-Accept: {_accept(key)}\r\n\r\n").encode())
        data = rest
        while True:
            frame, data = _read_frame(sock, data)
            if frame is None:
                return
            opcode, payload = frame
            if opcode == 0x8:
                return
            try:
                msg = json.loads(payload.decode())
                method = msg.get("method", "")
                out = json.dumps({"id": msg.get("id"),
                                  "result": {"echo": method}})
            except Exception:
                out = json.dumps({"id": None, "error": "bad request"})
            _write_frame(sock, 0x1, out.encode())


def _read_frame(sock, buf: bytes):
    while len(buf) < 2:
        c = sock.recv(4096)
        if not c:
            return None, buf
        buf += c
    b0, b1 = buf[0], buf[1]
    n = b1 & 0x7F
    masked = (b1 & 0x80) != 0
    idx = 2
    if n == 126:
        while len(buf) < idx + 2:
            buf += sock.recv(4096)
        n = struct.unpack("!H", buf[idx:idx + 2])[0]
        idx += 2
    elif n == 127:
        while len(buf) < idx + 8:
            buf += sock.recv(4096)
        n = struct.unpack("!Q", buf[idx:idx + 8])[0]
        idx += 8
    if masked:
        while len(buf) < idx + 4:
            buf += sock.recv(4096)
        mask = buf[idx:idx + 4]
        idx += 4
    while len(buf) < idx + n:
        c = sock.recv(4096)
        if not c:
            return None, buf
        buf += c
    payload = buf[idx:idx + n]
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return (b0 & 0x0F, payload), buf[idx + n:]


def _write_frame(sock, opcode: int, data: bytes) -> None:
    header = bytearray([0x80 | opcode])
    n = len(data)
    if n < 126:
        header.append(n)
    elif n < (1 << 16):
        header.append(126)
        header += struct.pack("!H", n)
    else:
        header.append(127)
        header += struct.pack("!Q", n)
    sock.sendall(bytes(header) + data)


def serve_echo(host: str = "127.0.0.1", port: int = 0):
    """Start (not running yet) an echo server. Returns (server, port)."""
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
    server = Server((host, port), _Handler)
    return server, server.server_address[1]
