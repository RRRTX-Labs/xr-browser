"""build/qa/compat/flow_classes.py — offline replay model for the compat corpus.

Each corpus entry names a `url_class`; the offline replay fixture must
genuinely exercise that class (a login flow fixture that has no password
field tests nothing). FLOW_MARKERS maps class -> HTML tokens the fixture
must contain. This is the offline half that runs here; the live half is
refused without XR_LIVE_NET=1 + an allowlisted host (tools/compat.py).
"""
from __future__ import annotations

FLOW_MARKERS: dict[str, list[str]] = {
    "login-flow": ["<form", 'type="password"'],
    "video-streaming": ["<video"],
    "upload-flow": ['type="file"'],
    "video-conferencing": ["<video", "RTCPeerConnection"],
    "search-engine": ['type="search"'],
    "webmail": ['role="list"'],
    "social-feed": ['role="feed"'],
    "e-commerce": ["<form", "<button"],
    "news-portal": ["<article", "<img"],
    "cloud-office": ["contenteditable"],
    "mapping": ['id="map"'],
    "banking": ['id="dashboard"'],
    "file-hosting": ['download'],
    "regional-portal": ['dir="rtl"'],
    "regional-marketplace": ["<form"],
    "regional-bank": ['type="password"'],
    "regional-video": ["<video"],
    "regional-news": ["<article"],
    "pdf-viewer": ['type="application/pdf"'],
    "printing": ["window.print"],
}

EXPECTATION_KEYS = {
    "visual", "console", "login", "media", "downloads", "bidi", "webrtc",
    "uploads", "print",
}
