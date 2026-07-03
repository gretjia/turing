#![forbid(unsafe_code)]

use std::path::PathBuf;

use turing_witness::export_tc3_corpus;

fn main() {
    let mut args = std::env::args_os().skip(1);
    let root = match args.next() {
        Some(path) => PathBuf::from(path),
        None => {
            eprintln!("usage: tc3-export <evidence-root>");
            std::process::exit(2);
        }
    };
    if args.next().is_some() {
        eprintln!("usage: tc3-export <evidence-root>");
        std::process::exit(2);
    }

    match export_tc3_corpus(&root) {
        Ok(report) => {
            println!(
                "TC3_EXPORT_PASS root={} programs={} halting={} nonhalting={}",
                report.root.display(),
                report.program_count,
                report.halting_program_count,
                report.nonhalting_program_count
            );
        }
        Err(error) => {
            eprintln!("TC3_EXPORT_FAIL {error}");
            std::process::exit(1);
        }
    }
}
