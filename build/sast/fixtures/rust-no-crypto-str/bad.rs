// SAST canary fixture — rust-no-crypto-str. Registered for P11 (no Rust
// code exists yet); proves the rule can turn red the moment .rs lands.
fn trigger() {
    let _ = str::crypto_aes_cbc("hand-rolled");   // banned: hand-rolled crypto
}
