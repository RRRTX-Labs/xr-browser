# Contract: Theme tokens v1 (§1.11 #14 part, R13)

- **Version:** 1. **Migration note:** `xr-schema-v1.md`.

## Declarative-only (R13)

A theme is **declarative JSON only** — a flat map of named tokens to values
(colors as `#rrggbb`/`#rrggbbaa`, spacing/radius as integers, font family as a
string). **No JavaScript, no code fields, no URLs to remote assets.** The token
name set is fixed per version; unknown tokens are rejected (strict). A contrast
validator (P8 theme fuzzer) runs against the token set; it is not part of the
freeze surface but consumes this contract.
