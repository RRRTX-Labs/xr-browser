// SAST canary fixture — ts-no-raw-crypto-vault. Never shipped.
// The vault WebUI client must hold no key material: cryptography lives in
// the vault daemon (P28). This fixture proves the rule can turn red.
export async function trigger(key: CryptoKey): Promise<ArrayBuffer> {
  return crypto.subtle.encrypt("AES-GCM", key, new Uint8Array(12)); // banned
}

export async function trigger2(raw: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt"]); // banned
}
