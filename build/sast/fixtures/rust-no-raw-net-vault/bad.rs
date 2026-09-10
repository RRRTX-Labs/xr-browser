// SAST canary fixture — rust-no-raw-net-vault. Registered for P11; the
// vault client may only egress through the guarded path, never raw sockets.
fn trigger() {
    let _ = std::net::TcpStream::connect("vault.example:443"); // banned: raw net
}
