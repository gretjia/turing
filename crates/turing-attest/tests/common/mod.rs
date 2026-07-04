//! Shared test support for `tests/tpm.rs` and `tests/divergence.rs`:
//! spawns a real `swtpm` simulator on a loopback TCP port pair, waits for
//! it to come up, and tears it down (kill the child + remove the temp
//! state dir) in `Drop`. No sudo; independent of `scripts/attest-tpm.sh`.
//!
//! `tests/common/mod.rs` (the `mod.rs` filename, inside a `common/`
//! subdirectory) is the standard cargo convention for test-support code
//! shared across multiple integration test binaries without cargo also
//! treating this file as its own test target.

use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::Duration;

/// Returned instead of a guard when `swtpm`/`swtpm_setup` are not on
/// `PATH`. Callers print `"SKIP: swtpm unavailable"` and return early per
/// SPEC B2 — in this workspace's dev environment swtpm IS installed, so
/// this arm is not expected to fire, but the fallback must still exist and
/// must never panic.
pub struct SwtpmUnavailable;

pub struct SwtpmGuard {
    child: Child,
    state_dir: PathBuf,
    tcti: String,
}

impl SwtpmGuard {
    pub fn tcti(&self) -> String {
        self.tcti.clone()
    }

    pub fn start() -> Result<SwtpmGuard, SwtpmUnavailable> {
        if which("swtpm").is_none() || which("swtpm_setup").is_none() {
            return Err(SwtpmUnavailable);
        }

        let state_dir = fresh_temp_dir("turing-attest-swtpm-state");
        std::fs::create_dir_all(&state_dir).expect("create swtpm state dir");

        let setup = Command::new("swtpm_setup")
            .arg("--tpm2")
            .arg("--tpmstate")
            .arg(&state_dir)
            .arg("--config")
            .arg("/dev/null")
            .arg("--createek")
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .output()
            .expect("spawn swtpm_setup");
        assert!(
            setup.status.success(),
            "swtpm_setup failed: {}",
            String::from_utf8_lossy(&setup.stderr)
        );

        let (data_port, ctrl_port) = free_port_pair();

        let child = Command::new("swtpm")
            .arg("socket")
            .arg("--tpmstate")
            .arg(format!("dir={}", state_dir.display()))
            .arg("--ctrl")
            .arg(format!("type=tcp,port={ctrl_port}"))
            .arg("--server")
            .arg(format!("type=tcp,port={data_port}"))
            .arg("--tpm2")
            .arg("--flags")
            .arg("not-need-init")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .expect("spawn swtpm socket");

        let tcti = format!("swtpm:host=localhost,port={data_port}");

        wait_for_port(data_port, Duration::from_secs(5));

        let startup = Command::new("tpm2_startup")
            .arg("-c")
            .env("TPM2TOOLS_TCTI", &tcti)
            .output()
            .expect("spawn tpm2_startup");
        assert!(
            startup.status.success(),
            "tpm2_startup failed: {}",
            String::from_utf8_lossy(&startup.stderr)
        );

        Ok(SwtpmGuard { child, state_dir, tcti })
    }
}

impl Drop for SwtpmGuard {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = std::fs::remove_dir_all(&self.state_dir);
    }
}

fn which(bin: &str) -> Option<PathBuf> {
    std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths).map(|dir| dir.join(bin)).find(|p| p.is_file())
    })
}

fn fresh_temp_dir(prefix: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    std::env::temp_dir().join(format!("{prefix}-{}-{}", std::process::id(), nanos))
}

/// Binds an ephemeral port to discover a free one, releases it, then
/// checks port+1 (the control-channel convention `tcti-swtpm` expects) is
/// free too. A small TOCTOU race window between "found free" and "swtpm
/// binds it" is an accepted latitude for local dev/test use (SPEC.md:
/// "pick whichever TCTI connects to reliably").
fn free_port_pair() -> (u16, u16) {
    loop {
        let data_listener = TcpListener::bind("127.0.0.1:0").expect("bind ephemeral port");
        let data = data_listener.local_addr().expect("local_addr").port();
        drop(data_listener);
        if let Ok(ctrl_listener) = TcpListener::bind(("127.0.0.1", data + 1)) {
            drop(ctrl_listener);
            return (data, data + 1);
        }
    }
}

fn wait_for_port(port: u16, timeout: Duration) {
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if std::net::TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    panic!("swtpm data port {port} never became reachable within {timeout:?}");
}
