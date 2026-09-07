"""cdp.py — minimal WebSocket / CDP client, stdlib only (P4 dependency rule).

Why hand-rolled: the phase forbids new dependencies, vendored or otherwise,
and the farm driver needs to talk CDP to read `chrome://process-internals`
data (and `--enable-logging` output) after launching a built browser. A
WebSocket client is ~150 lines of RFC 6455; a vendored `websockets` wheel is a
supply-chain surface we do not need.

Implements exactly what the driver uses:
  * the opening handshake (HTTP/1.1 Upgrade, Sec-WebSocket-Key/Accept)
  * masked client text frames (< 126 B and 126..64KiB and 64-bit lengths)
  * unmasked server frames, including fragmented (FIN=0) reassembly
  * ping/pong and the close handshake (opcodes 0x9/0xA/0x8)

Explicitly NOT implemented: permessage-deflate, TLS, proxies. The driver
talks to 127.0.0.1 over plain ws://, and a missing feature must fail loudly
rather than be half-supported.

Unit-tested against a loopback fixture server in
build/spike/tests/test_cdp.py (handshake, masking, fragmentation, close).
"""
from __future__ import annotations

import base64
import hashlib
import json
import socket
import struct
from typing import Any

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BINARY = 0x0, 0x1, 0x2
OP_CLOSE, OP_PING, OP_PONG = 0x8, 0x9, 0xA


class CdpError(RuntimeError):
    """Protocol or transport failure. Never retried silently."""


class WebSocket:
    """A blocking RFC 6455 client. One instance per connection."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buf = b""

    # -- handshake ----------------------------------------------------
    @classmethod
    def connect(cls, host: str, port: int, path: str = "/",
                timeout: float = 5.0) -> "WebSocket":
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise CdpError(f"refusing non-loopback target {host!r}: the driver "
                           "only ever talks to the browser it launched")
        key = base64.b64encode(_rand16()).decode()
        req = (f"GET {path} HTTP/1.1\r\n"
               f"Host: {host}:{port}\r\n"
               "Upgrade: websocket\r\n"
               "Connection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n").encode()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.sendall(req)
        ws = cls(sock)
        header = ws._read_until(b"\r\n\r\n")
        if b"101" not in header.split(b"\r\n", 1)[0]:
            raise CdpError(f"handshake failed: {header[:120]!r}")
        accept = _accept_key(key).encode()
        if accept not in header:
            raise CdpError("handshake Sec-WebSocket-Accept mismatch")
        return ws

    # -- transport ----------------------------------------------------
    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CdpError("connection closed during handshake")
            self._buf += chunk
        head, _, rest = self._buf.partition(marker)
        self._buf = rest
        return head + marker

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CdpError("connection closed mid-frame")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    # -- framing ------------------------------------------------------
    def send_text(self, payload: str) -> None:
        self._send_frame(OP_TEXT, payload.encode("utf-8"), mask=True)

    def _send_frame(self, opcode: int, data: bytes, *, mask: bool) -> None:
        header = bytearray([0x80 | opcode])          # FIN + opcode
        n = len(data)
        mask_bit = 0x80 if mask else 0x00
        if n < 126:
            header.append(mask_bit | n)
        elif n < (1 << 16):
            header.append(mask_bit | 126)
            header += struct.pack("!H", n)
        else:
            header.append(mask_bit | 127)
            header += struct.pack("!Q", n)
        if mask:
            key = _rand4()
            masked = bytes(b ^ key[i % 4] for i, b in enumerate(data))
            self.sock.sendall(bytes(header) + key + masked)
        else:
            self.sock.sendall(bytes(header) + data)

    def recv_text(self) -> str:
        """Read one complete message (reassembles fragmented frames)."""
        data = b""
        while True:
            opcode, payload = self._recv_frame()
            if opcode == OP_CONT:
                data += payload
                continue
            if opcode == OP_TEXT:
                return (data + payload).decode("utf-8")
            if opcode == OP_PING:
                self._send_frame(OP_PONG, payload, mask=True)
                continue
            if opcode == OP_CLOSE:
                raise CdpError("peer closed the connection")
            raise CdpError(f"unsupported opcode 0x{opcode:x}")

    def _recv_frame(self) -> tuple[int, bytes]:
        b0, b1 = self._recv_exact(2)
        fin, opcode = (b0 & 0x80) != 0, b0 & 0x0F
        masked = (b1 & 0x80) != 0
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack("!H", self._recv_exact(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(n)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if not fin and opcode == OP_CONT:
            return OP_CONT, payload
        return opcode, payload

    def close(self) -> None:
        try:
            self._send_frame(OP_CLOSE, struct.pack("!H", 1000), mask=True)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


# --- CDP convenience ---------------------------------------------------------

class Cdp:
    """Tiny JSON-RPC shim over WebSocket (only what the driver needs)."""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self._id = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._id += 1
        self.ws.send_text(json.dumps({"id": self._id, "method": method,
                                      "params": params or {}}))
        deadline = 0
        while deadline < 200:                       # skip events/notifications
            msg = json.loads(self.ws.recv_text())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise CdpError(f"CDP {method} error: {msg['error']}")
                return msg.get("result", {})
            deadline += 1
        raise CdpError(f"no response to {method} after {deadline} messages")


def _rand16() -> bytes:
    import os
    return os.urandom(16)


def _rand4() -> bytes:
    import os
    return os.urandom(4)


def _accept_key(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode()).digest()
    return base64.b64encode(digest).decode()
