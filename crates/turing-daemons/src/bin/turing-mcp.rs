use turing_daemons::{DaemonContract, run_daemon};

fn main() -> std::process::ExitCode {
    run_daemon(DaemonContract {
        role: "turing-mcp",
        can_move_accepted_head: false,
    })
}
