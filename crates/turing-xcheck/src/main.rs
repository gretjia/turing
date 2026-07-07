use std::io::{self, Read};

use turing_contracts::jcs;

fn main() {
    if let Err(err) = run() {
        eprintln!("turing-xcheck: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input)?;

    let mut case_index = 0usize;
    for raw_line in input.lines() {
        let line = raw_line.trim_end_matches('\r');
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        case_index += 1;
        let value = jcs::parse_strict(line)?;
        let bytes = jcs::canonicalize(&value)?;
        println!("{case_index}\t{}", lower_hex(&bytes));
    }
    Ok(())
}

fn lower_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::lower_hex;

    #[test]
    fn lower_hex_encodes_bytes() {
        assert_eq!(lower_hex(b"a:\x00\xff"), "613a00ff");
    }
}
