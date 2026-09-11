//! xr-updateserver — the DEPLOYABLE XR update server (P10-T2).
//!
//! std-only Rust (`#![forbid(unsafe_code)]`, ZERO external crates — the
//! §research 7 outcome: a std-only server needs no dependency, which is
//! the security win, not a limitation). It implements EXACTLY the surface
//! of `release/server/refimpl/update_server_ref.py` per
//! `release/server/spec/render-31.md`; `tests/conformance.rs` replays the
//! committed corpus (`release/server/tests/conformance.json`) and a byte
//! of divergence from the reference is a red gate.
//!
//! No network, no state, no accounts, no logging: `handle()` is pure.

#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::fmt::Write as _;

pub mod spec_generated;
pub use spec_generated::SPEC_VARIANTS;

pub const REQUEST_CAP: usize = 65536;
pub const PREFIX: &str = ")]}'\n";
pub const APP_ID: &str = "labs.rrrtx.xr";
pub const MAX_APPID: usize = 128;

/// TEST-ONLY stub key material (mirrors the client test fixture + the
/// reference's KEY_MATERIAL; no real keys exist — ADR-0004, HG-36).
pub const KEY_MATERIAL: &[(&str, &str)] = &[
    ("xr-root-1", "ROOT-PUB"),
    ("xr-signing-2026-09", "SIGNING-PUB"),
];

// ---------------------------------------------------------------- JSON --

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    /// Raw text of the number, preserved verbatim (canonical render = the
    /// digits as written; JSON forbids leading zeros so parity holds).
    Num(String),
    Str(String),
    Arr(Vec<Value>),
    /// Insertion-ordered entries; canonical() sorts at render time.
    Obj(Vec<(String, Value)>),
}

fn skip_ws(b: &[u8], i: &mut usize) {
    while *i < b.len() && matches!(b[*i], b' ' | b'\t' | b'\n' | b'\r') {
        *i += 1;
    }
}

fn starts_with(b: &[u8], i: usize, lit: &str) -> bool {
    b[i..].starts_with(lit.as_bytes())
}

fn utf8_len(c: u8) -> usize {
    if c < 0x80 {
        1
    } else if c >= 0xF0 {
        4
    } else if c >= 0xE0 {
        3
    } else if c >= 0xC0 {
        2
    } else {
        0
    }
}

fn parse_hex4(b: &[u8], i: &mut usize) -> Option<u32> {
    let mut v: u32 = 0;
    for _ in 0..4 {
        let c = *b.get(*i)?;
        *i += 1;
        let d = (c as char).to_digit(16)?;
        v = v * 16 + d;
    }
    Some(v)
}

fn parse_str_raw(b: &[u8], i: &mut usize) -> Option<String> {
    if b.get(*i) != Some(&b'"') {
        return None;
    }
    *i += 1;
    let mut out = String::new();
    loop {
        let c = *b.get(*i)?;
        *i += 1;
        match c {
            b'"' => return Some(out),
            b'\\' => {
                let e = *b.get(*i)?;
                *i += 1;
                match e {
                    b'"' => out.push('"'),
                    b'\\' => out.push('\\'),
                    b'/' => out.push('/'),
                    b'b' => out.push('\u{0008}'),
                    b'f' => out.push('\u{000C}'),
                    b'n' => out.push('\n'),
                    b'r' => out.push('\r'),
                    b't' => out.push('\t'),
                    b'u' => {
                        let cp = parse_hex4(b, i)?;
                        if (0xD800..0xDC00).contains(&cp) {
                            if b.get(*i) != Some(&b'\\') {
                                return None;
                            }
                            *i += 1;
                            if b.get(*i) != Some(&b'u') {
                                return None;
                            }
                            *i += 1;
                            let lo = parse_hex4(b, i)?;
                            if !(0xDC00..0xE000).contains(&lo) {
                                return None;
                            }
                            let c = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                            out.push(char::from_u32(c)?);
                        } else if (0xDC00..0xE000).contains(&cp) {
                            return None;
                        } else {
                            out.push(char::from_u32(cp)?);
                        }
                    }
                    _ => return None,
                }
            }
            _ => {
                let len = utf8_len(c);
                if len == 0 {
                    return None;
                }
                if len == 1 && c < 0x20 {
                    return None; // raw control chars are not JSON
                }
                let start = *i - 1;
                *i = start + len;
                if *i > b.len() {
                    return None;
                }
                out.push_str(std::str::from_utf8(&b[start..*i]).ok()?);
            }
        }
    }
}

fn parse_num(b: &[u8], i: &mut usize) -> Option<Value> {
    let start = *i;
    if b.get(*i) == Some(&b'-') {
        *i += 1;
    }
    let dig_start = *i;
    while *i < b.len() && b[*i].is_ascii_digit() {
        *i += 1;
    }
    if *i == dig_start {
        return None;
    }
    if b.get(*i) == Some(&b'.') {
        *i += 1;
        let fs = *i;
        while *i < b.len() && b[*i].is_ascii_digit() {
            *i += 1;
        }
        if *i == fs {
            return None;
        }
    }
    if matches!(b.get(*i), Some(&b'e') | Some(&b'E')) {
        *i += 1;
        if matches!(b.get(*i), Some(&b'+') | Some(&b'-')) {
            *i += 1;
        }
        let es = *i;
        while *i < b.len() && b[*i].is_ascii_digit() {
            *i += 1;
        }
        if *i == es {
            return None;
        }
    }
    Some(Value::Num(
        String::from_utf8_lossy(&b[start..*i]).into_owned(),
    ))
}

fn parse_value(b: &[u8], i: &mut usize) -> Option<Value> {
    skip_ws(b, i);
    match *b.get(*i)? {
        b'{' => parse_obj(b, i),
        b'[' => parse_arr(b, i),
        b'"' => parse_str_raw(b, i).map(Value::Str),
        b't' => {
            if starts_with(b, *i, "true") {
                *i += 4;
                Some(Value::Bool(true))
            } else {
                None
            }
        }
        b'f' => {
            if starts_with(b, *i, "false") {
                *i += 5;
                Some(Value::Bool(false))
            } else {
                None
            }
        }
        b'n' => {
            if starts_with(b, *i, "null") {
                *i += 4;
                Some(Value::Null)
            } else {
                None
            }
        }
        _ => parse_num(b, i),
    }
}

fn parse_arr(b: &[u8], i: &mut usize) -> Option<Value> {
    *i += 1; // '['
    let mut out = Vec::new();
    skip_ws(b, i);
    if b.get(*i) == Some(&b']') {
        *i += 1;
        return Some(Value::Arr(out));
    }
    loop {
        let v = parse_value(b, i)?;
        out.push(v);
        skip_ws(b, i);
        match b.get(*i)? {
            b',' => *i += 1,
            b']' => {
                *i += 1;
                return Some(Value::Arr(out));
            }
            _ => return None,
        }
    }
}

fn parse_obj(b: &[u8], i: &mut usize) -> Option<Value> {
    *i += 1; // '{'
    let mut out: Vec<(String, Value)> = Vec::new();
    skip_ws(b, i);
    if b.get(*i) == Some(&b'}') {
        *i += 1;
        return Some(Value::Obj(out));
    }
    loop {
        skip_ws(b, i);
        if b.get(*i) != Some(&b'"') {
            return None;
        }
        let k = parse_str_raw(b, i)?;
        skip_ws(b, i);
        if b.get(*i) != Some(&b':') {
            return None;
        }
        *i += 1;
        let v = parse_value(b, i)?;
        out.push((k, v));
        skip_ws(b, i);
        match b.get(*i)? {
            b',' => *i += 1,
            b'}' => {
                *i += 1;
                return Some(Value::Obj(out));
            }
            _ => return None,
        }
    }
}

pub fn parse_json(s: &str) -> Option<Value> {
    let b = s.as_bytes();
    let mut i = 0usize;
    let v = parse_value(b, &mut i)?;
    skip_ws(b, &mut i);
    if i != b.len() {
        return None;
    }
    Some(v)
}

pub fn escape_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        let cp = c as u32;
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{0008}' => out.push_str("\\b"),
            '\u{000C}' => out.push_str("\\f"),
            c if cp < 0x20 || cp > 0x7E => {
                if cp > 0xFFFF {
                    let v = cp - 0x10000;
                    let _ = write!(out, "\\u{:04x}\\u{:04x}",
                                   0xD800 + (v >> 10), 0xDC00 + (v & 0x3FF));
                } else {
                    let _ = write!(out, "\\u{:04x}", cp);
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

pub fn canonical(v: &Value) -> String {
    match v {
        Value::Null => "null".to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Num(s) => s.clone(),
        Value::Str(s) => escape_str(s),
        Value::Arr(items) => {
            let parts: Vec<String> = items.iter().map(canonical).collect();
            format!("[{}]", parts.join(","))
        }
        Value::Obj(entries) => {
            // last-wins on duplicate keys (same as a Python dict load)
            let mut sorted: BTreeMap<&str, &Value> = BTreeMap::new();
            for (k, val) in entries {
                sorted.insert(k.as_str(), val);
            }
            let parts: Vec<String> = sorted
                .iter()
                .map(|(k, val)| format!("{}:{}", escape_str(k), canonical(val)))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
    }
}

// object/string/int accessors (spec navigation) ---------------------------
pub fn get<'a>(v: &'a Value, key: &str) -> Option<&'a Value> {
    match v {
        Value::Obj(entries) => {
            entries.iter().find(|(k, _)| k == key).map(|(_, x)| x)
        }
        _ => None,
    }
}

pub fn as_str<'a>(v: &'a Value) -> Option<&'a str> {
    match v {
        Value::Str(s) => Some(s),
        _ => None,
    }
}

fn as_int(v: &Value) -> Option<i64> {
    match v {
        // corpus + spec integers are plain decimal; bools are NOT ints
        // (Python's isinstance(bool, int) trap is mirrored by the caller).
        Value::Num(s) => s.parse().ok(),
        _ => None,
    }
}

/// Python `repr()` of a scalar — the detail strings are CONTRACT BYTES
/// (the corpus pins them), so error text must match the reference exactly.
fn py_repr(v: &Value) -> String {
    match v {
        Value::Str(s) => format!("'{}'", s),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Null => "None".to_string(),
        Value::Num(n) => n.clone(),
        // containers never reach a detail string in the corpus; render the
        // canonical JSON rather than panicking.
        other => canonical(other),
    }
}

// --------------------------------------------------------------- SHA-256 --

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f,
        0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    let bitlen = (data.len() as u64).wrapping_mul(8);
    let mut msg = data.to_vec();
    msg.push(0x80);
    while msg.len() % 64 != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bitlen.to_be_bytes());
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for j in 0..16 {
            w[j] = u32::from_be_bytes([
                chunk[j * 4],
                chunk[j * 4 + 1],
                chunk[j * 4 + 2],
                chunk[j * 4 + 3],
            ]);
        }
        for j in 16..64 {
            let s0 = w[j - 15].rotate_right(7) ^ w[j - 15].rotate_right(18)
                ^ (w[j - 15] >> 3);
            let s1 = w[j - 2].rotate_right(17) ^ w[j - 2].rotate_right(19)
                ^ (w[j - 2] >> 10);
            w[j] = w[j - 16]
                .wrapping_add(s0)
                .wrapping_add(w[j - 7])
                .wrapping_add(s1);
        }
        let (mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh) =
            (h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]);
        for j in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ ((!e) & g);
            let t1 = hh
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[j])
                .wrapping_add(w[j]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        h[0] = h[0].wrapping_add(a);
        h[1] = h[1].wrapping_add(b);
        h[2] = h[2].wrapping_add(c);
        h[3] = h[3].wrapping_add(d);
        h[4] = h[4].wrapping_add(e);
        h[5] = h[5].wrapping_add(f);
        h[6] = h[6].wrapping_add(g);
        h[7] = h[7].wrapping_add(hh);
    }
    let mut out = [0u8; 32];
    for (i, word) in h.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}

pub fn stub_sig(material: &str, message: &str) -> String {
    let mut buf = Vec::with_capacity(material.len() + 1 + message.len());
    buf.extend_from_slice(material.as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(message.as_bytes());
    let digest = sha256(&buf);
    let mut hex = String::with_capacity(32);
    for byte in digest.iter().take(16) {
        let _ = write!(hex, "{:02x}", byte);
    }
    format!("sig:{}", hex)
}

fn key_material(key_id: &str) -> Option<&'static str> {
    KEY_MATERIAL
        .iter()
        .find(|(k, _)| *k == key_id)
        .map(|(_, m)| *m)
}

// ---------------------------------------------------------------- spec --

/// Loads the named spec variant ("base", "pause-beta", "revoke-active").
pub fn spec_value(name: &str) -> Option<Value> {
    let (_, blob) = SPEC_VARIANTS.iter().find(|(n, _)| *n == name)?;
    parse_json(blob)
}

pub fn parse_version(v: &str) -> Option<[u16; 4]> {
    let parts: Vec<&str> = v.split('.').collect();
    if parts.len() != 4 {
        return None;
    }
    let mut out = [0u16; 4];
    for (idx, p) in parts.iter().enumerate() {
        if p.is_empty() || !p.chars().all(|c| c.is_ascii_digit()) {
            return None;
        }
        if p.len() > 1 && p.starts_with('0') {
            return None; // non-canonical leading zero
        }
        let n: u32 = p.parse().ok()?;
        if n > 65535 {
            return None;
        }
        out[idx] = n as u16;
    }
    Some(out)
}

fn err(status: u16, code: &str, detail: &str) -> (u16, String) {
    let obj = Value::Obj(vec![
        ("detail".to_string(), Value::Str(detail.to_string())),
        ("error".to_string(), Value::Str(code.to_string())),
    ]);
    (status, format!("{}\n", canonical(&obj)))
}

const CHANNELS: [&str; 4] = ["nightly", "beta", "stable", "dev"];

fn is_channel(v: &Value) -> bool {
    match as_str(v) {
        Some(s) => CHANNELS.contains(&s),
        None => false,
    }
}

/// The pure request → (http_status, response_bytes) core. Both backends
/// MUST agree byte-for-byte on the committed corpus.
pub fn handle(frame: &[u8], spec: &Value,
              content_length: Option<usize>) -> (u16, String) {
    if frame.len() > REQUEST_CAP {
        return err(400, "kTooLarge",
                   &format!("request above {} cap", REQUEST_CAP));
    }
    if let Some(cl) = content_length {
        if cl > frame.len() {
            return err(400, "kTruncated",
                       &format!("content-length {} > body {}", cl, frame.len()));
        }
        if cl < frame.len() {
            return err(400, "kBadLength",
                       &format!("content-length {} < body {}", cl, frame.len()));
        }
    }
    let full = String::from_utf8_lossy(frame).into_owned();
    let mut body: &str = &full;
    if body.starts_with(PREFIX) {
        body = &body[PREFIX.len()..];
    }
    let req = match parse_json(body) {
        Some(v) => v,
        None => return err(400, "kMalformedRequest", "bad json"),
    };
    let entries = match &req {
        Value::Obj(e) => e,
        _ => return err(400, "kMalformedRequest", "request not an object"),
    };
    let has = |key: &str| entries.iter().any(|(k, _)| k == key);
    if entries.len() != 3 || !has("protocol") || !has("os") || !has("app") {
        return err(400, "kUnknownField",
                   "request keys must be exactly protocol/os/app");
    }
    let protocol = get(&req, "protocol").cloned().unwrap_or(Value::Null);
    if as_str(&protocol) != Some("3.1") {
        return err(400, "kWrongProtocol",
                   &format!("protocol {}", py_repr(&protocol)));
    }
    match get(&req, "os") {
        Some(Value::Obj(_)) => {}
        _ => return err(400, "kMalformedRequest", "os must be an object"),
    }
    let apps = match get(&req, "app") {
        Some(Value::Arr(a)) if !a.is_empty() => a,
        _ => return err(400, "kMalformedRequest", "app must be a non-empty array"),
    };

    let vg = get(get(spec, "version-graph").expect("spec: version-graph"),
                 "channels").expect("spec: version-graph.channels");
    let ch_spec = get(get(spec, "channels").expect("spec: channels"),
                      "channels").expect("spec: channels.channels");
    let cohorts = get(get(spec, "cohorts").expect("spec: cohorts"),
                      "per_channel").expect("spec: cohorts.per_channel");
    let active = get(get(spec, "epochs").expect("spec: epochs"),
                     "active").expect("spec: epochs.active");
    let revoked = get(get(spec, "epochs").expect("spec: epochs"),
                      "revoked").expect("spec: epochs.revoked");

    let mut out_apps: Vec<Value> = Vec::new();
    for app in apps {
        let app_entries = match app {
            Value::Obj(e) => e,
            _ => return err(400, "kUnknownField", "bad app entry"),
        };
        if app_entries.iter().any(|(k, _)| {
            !matches!(k.as_str(), "appid" | "version" | "channel" | "bucket"
                      | "epoch")
        }) {
            return err(400, "kUnknownField", "bad app entry");
        }
        let appid_v = get(app, "appid").cloned().unwrap_or(Value::Null);
        let appid = match as_str(&appid_v) {
            Some(s) if !s.is_empty() && s.len() <= MAX_APPID => s,
            _ => {
                return err(400, "kBadAppid",
                           &format!("appid {}", py_repr(&appid_v)))
            }
        };
        let channel_v = get(app, "channel").cloned().unwrap_or(Value::Null);
        if !is_channel(&channel_v) {
            return err(400, "kBadChannel",
                       &format!("channel {}", py_repr(&channel_v)));
        }
        let channel = as_str(&channel_v).unwrap_or("");
        let bucket_v = get(app, "bucket").cloned().unwrap_or(Value::Null);
        let bucket = match &bucket_v {
            Value::Num(_) => as_int(&bucket_v),
            _ => None, // bools/strings/null are NOT ints (Python mirror)
        };
        let bucket = match bucket {
            Some(b) if (0..=99).contains(&b) => b,
            _ => return err(400, "kBadBucket",
                            &format!("bucket {}", py_repr(&bucket_v))),
        };
        let epoch: Option<&str> = match get(app, "epoch") {
            None | Some(Value::Null) => None,
            Some(Value::Str(s)) => Some(s),
            Some(_) => {
                return err(400, "kUnknownField", "epoch must be a string")
            }
        };
        if let Value::Obj(os_entries) = get(&req, "os").unwrap_or(&Value::Null)
        {
            if os_entries.iter().any(|(k, _)| {
                !matches!(k.as_str(), "platform" | "version" | "arch")
            }) {
                return err(400, "kUnknownField", "bad os entry");
            }
        }

        let served = get(get(ch_spec, channel).unwrap_or(&Value::Null),
                         "served").and_then(as_bool);
        let paused = get(get(ch_spec, channel).unwrap_or(&Value::Null),
                         "paused").and_then(as_bool);
        let ramp = get(get(cohorts, channel).unwrap_or(&Value::Null),
                       "ramp_percent").and_then(as_int);
        let (served, paused, ramp) = match (served, paused, ramp) {
            (Some(s), Some(p), Some(r)) => (s, p, r),
            _ => return err(400, "kBadChannel",
                            &format!("channel {}", py_repr(&channel_v))),
        };

        let mut entry_entries: Vec<(String, Value)> =
            vec![("appid".to_string(), Value::Str(appid.to_string()))];
        if appid != APP_ID {
            entry_entries.push((
                "status".to_string(),
                Value::Str("error-unknownApplication".to_string()),
            ));
            out_apps.push(Value::Obj(entry_entries));
            continue;
        }
        let mut uc_entries: Vec<(String, Value)> = Vec::new();
        if !served {
            uc_entries.push(("status".to_string(),
                             Value::Str("noupdate".to_string())));
        } else if paused {
            let sem = as_str(get(spec, "channels")
                .and_then(|c| get(c, "pause_semantics"))
                .unwrap_or(&Value::Null))
                .unwrap_or("error-pausedChannel");
            uc_entries.push(("status".to_string(),
                             Value::Str(sem.to_string())));
        } else if epoch.map_or(false, |e| {
            match revoked {
                Value::Arr(items) => items.iter().any(|r| {
                    as_str(get(r, "epoch_id").unwrap_or(&Value::Null))
                        == Some(e)
                }),
                _ => false,
            }
        }) {
            uc_entries.push(("status".to_string(),
                             Value::Str("error-epochRevoked".to_string())));
        } else if ramp <= bucket {
            uc_entries.push(("status".to_string(),
                             Value::Str("noupdate".to_string())));
        } else {
            let rawv = match get(app, "version") {
                Some(v) => v.clone(),
                None => Value::Str(String::new()),
            };
            let cur = match as_str(&rawv).and_then(parse_version) {
                Some(v) => v,
                None => {
                    return err(400, "kBadVersion",
                               &format!("version {} non-canonical",
                                        py_repr(&rawv)))
                }
            };
            let head = get(get(vg, channel).unwrap_or(&Value::Null), "head")
                .expect("spec: channel head");
            let hv = parse_version(as_str(get(head, "version")
                .unwrap_or(&Value::Null)).unwrap_or(""))
                .expect("spec: head version canonical");
            if cur >= hv {
                uc_entries.push(("status".to_string(),
                                 Value::Str("noupdate".to_string())));
            } else {
                let version = as_str(get(head, "version")
                    .unwrap_or(&Value::Null)).unwrap_or("").to_string();
                let hash = as_str(get(head, "hash_sha256")
                    .unwrap_or(&Value::Null)).unwrap_or("").to_string();
                let size = as_int(get(head, "size")
                    .unwrap_or(&Value::Null)).unwrap_or(0);
                let url = as_str(get(head, "url")
                    .unwrap_or(&Value::Null)).unwrap_or("").to_string();
                let package = Value::Obj(vec![
                    ("fp".to_string(), Value::Str(version.clone())),
                    ("hash_sha256".to_string(), Value::Str(hash)),
                    ("name".to_string(),
                     Value::Str(format!("xr-{}.crx", version))),
                    ("size".to_string(), Value::Num(size.to_string())),
                ]);
                let manifest = Value::Obj(vec![
                    ("packages".to_string(),
                     Value::Obj(vec![("package".to_string(),
                                      Value::Arr(vec![package]))])),
                    ("run".to_string(), Value::Str(String::new())),
                    ("version".to_string(), Value::Str(version.clone())),
                ]);
                uc_entries.push(("manifest".to_string(), manifest));
                uc_entries.push(("status".to_string(),
                                 Value::Str("ok".to_string())));
                uc_entries.push(("urls".to_string(), Value::Obj(vec![
                    ("url".to_string(), Value::Arr(vec![Value::Obj(vec![
                        ("codebase".to_string(), Value::Str(url)),
                    ])])),
                ])));
            }
        }
        entry_entries.push(("status".to_string(),
                            Value::Str("ok".to_string())));
        entry_entries.push(("updatecheck".to_string(),
                            Value::Obj(uc_entries)));
        out_apps.push(Value::Obj(entry_entries));
    }

    let response = Value::Obj(vec![
        ("app".to_string(), Value::Arr(out_apps)),
        ("daystart".to_string(), Value::Obj(vec![
            ("elapsed_days".to_string(), Value::Num("0".to_string())),
        ])),
        ("protocol".to_string(), Value::Str("3.1".to_string())),
        ("server".to_string(), Value::Str("pub".to_string())),
    ]);
    let active_id = as_str(get(active, "epoch_id")
        .unwrap_or(&Value::Null)).unwrap_or("").to_string();
    let active_key = as_str(get(active, "key_id")
        .unwrap_or(&Value::Null)).unwrap_or("").to_string();
    let active_seq = as_int(get(active, "seq").unwrap_or(&Value::Null))
        .unwrap_or(0);
    let material = key_material(&active_key)
        .expect("spec: active epoch key material must be pinned in \
                 KEY_MATERIAL");
    let sig = stub_sig(material, &canonical(&response));
    let envelope = Value::Obj(vec![
        ("epoch".to_string(), Value::Obj(vec![
            ("epoch_id".to_string(), Value::Str(active_id)),
            ("key_id".to_string(), Value::Str(active_key)),
            ("seq".to_string(), Value::Num(active_seq.to_string())),
        ])),
        ("response".to_string(), response),
        ("schema".to_string(),
         Value::Str("xr-update-envelope".to_string())),
        ("schema_version".to_string(), Value::Num("1".to_string())),
        ("signature".to_string(), Value::Obj(vec![
            ("alg".to_string(),
             Value::Str("minisign-ed25519".to_string())),
            ("key_id".to_string(), Value::Str(active_key.clone())),
            ("sig".to_string(), Value::Str(sig)),
        ])),
    ]);
    (200, format!("{}{}\n", PREFIX, canonical(&envelope)))
}

// ----------------------------------------------------------- self-check --

/// Mirrors the reference's --self-check invariants. Returns Err(reason).
pub fn self_check() -> Result<usize, String> {
    let spec = spec_value("base").ok_or("spec variant 'base' missing")?;
    let req = canonical(&Value::Obj(vec![
        ("app".to_string(), Value::Arr(vec![Value::Obj(vec![
            ("appid".to_string(), Value::Str(APP_ID.to_string())),
            ("bucket".to_string(), Value::Num("0".to_string())),
            ("channel".to_string(), Value::Str("nightly".to_string())),
            ("version".to_string(),
             Value::Str("0.9.21.0".to_string())),
        ])])),
        ("os".to_string(), Value::Obj(vec![
            ("platform".to_string(), Value::Str("linux".to_string())),
        ])),
        ("protocol".to_string(), Value::Str("3.1".to_string())),
    ]));
    let (status, out) = handle(req.as_bytes(), &spec, None);
    if status != 200 {
        return Err(format!("happy path status {}", status));
    }
    if !out.starts_with(PREFIX) || !out.ends_with('\n') {
        return Err("response missing prefix/trailing newline".to_string());
    }
    let env = parse_json(out[PREFIX.len()..].trim_end())
        .ok_or("response not re-parseable")?;
    if canonical(&env) + "\n" != out[PREFIX.len()..] {
        return Err("response not canonical".to_string());
    }
    let key_id = as_str(get(get(&env, "signature").unwrap_or(&Value::Null),
                            "key_id").unwrap_or(&Value::Null))
        .unwrap_or("");
    let material = key_material(key_id).ok_or("unknown key_id")?;
    let response = get(&env, "response").ok_or("no response")?;
    if as_str(get(get(&env, "signature").unwrap_or(&Value::Null), "sig")
        .unwrap_or(&Value::Null)).unwrap_or("")
        != stub_sig(material, &canonical(response))
    {
        return Err("self signature mismatch".to_string());
    }
    if out.len() > 2048 {
        return Err(format!("response {} > 2048", out.len()));
    }
    // statelessness
    if handle(req.as_bytes(), &spec, None) != (status, out.clone()) {
        return Err("stateful: second handle differs".to_string());
    }
    // typed refusals
    let bad = canonical(&Value::Obj(vec![
        ("app".to_string(), Value::Arr(vec![Value::Obj(vec![
            ("appid".to_string(), Value::Str(APP_ID.to_string())),
            ("bucket".to_string(), Value::Num("0".to_string())),
            ("channel".to_string(), Value::Str("nightly".to_string())),
            ("version".to_string(),
             Value::Str("0.9.21.0".to_string())),
        ])])),
        ("extra".to_string(), Value::Num("1".to_string())),
        ("os".to_string(), Value::Obj(vec![])),
        ("protocol".to_string(), Value::Str("3.1".to_string())),
    ]));
    if handle(bad.as_bytes(), &spec, None).0 != 400 {
        return Err("unknown field not refused".to_string());
    }
    let big = vec![b'x'; REQUEST_CAP + 1];
    if handle(&big, &spec, None).0 != 400 {
        return Err("cap not enforced".to_string());
    }
    Ok(out.len())
}
