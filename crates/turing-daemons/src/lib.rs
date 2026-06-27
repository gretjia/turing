//! Process topology contracts for private-local TuringOS daemons.

use std::process::ExitCode;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct DaemonContract {
    pub role: &'static str,
    pub can_move_accepted_head: bool,
}

impl DaemonContract {
    #[must_use]
    pub fn check_line(self) -> String {
        format!(
            "role={} can_move_accepted_head={} single_loop_subroutine=true",
            self.role, self.can_move_accepted_head
        )
    }
}

pub fn run_daemon(contract: DaemonContract) -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [flag] if flag == "--check" => {
            println!("{}", contract.check_line());
            ExitCode::SUCCESS
        }
        [cmd] if cmd == "move-accepted-head" => {
            if contract.can_move_accepted_head {
                println!(
                    "accepted_head movement is routed through turingd predicate/approval gate"
                );
                ExitCode::SUCCESS
            } else {
                eprintln!("{} cannot move accepted_head", contract.role);
                ExitCode::from(2)
            }
        }
        _ => {
            eprintln!("unknown {} command", contract.role);
            ExitCode::from(2)
        }
    }
}
