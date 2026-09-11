//! xr-updateserver CLI — thin wrapper over the lib (see src/lib.rs).
//! `--self-check` | `--conformance <corpus.json>` | `--handle <frame-file>`
#![forbid(unsafe_code)]

use std::process::ExitCode;

use xr_updateserver::{as_str, get, handle, parse_json, self_check,
                     spec_value, Value};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).map(String::as_str).unwrap_or("");
    match mode {
        "--self-check" => match self_check() {
            Ok(n) => {
                println!("PASS: xr-updateserver self-check (response {} bytes; \
                          render+verify+statelessness+cap)", n);
                ExitCode::SUCCESS
            }
            Err(reason) => {
                println!("FAIL: self-check: {}", reason);
                ExitCode::FAILURE
            }
        },
        "--conformance" => {
            let path = match args.get(2) {
                Some(p) => p.clone(),
                None => {
                    eprintln!("usage: xr-updateserver --conformance <file>");
                    return ExitCode::from(2);
                }
            };
            match run_conformance(&path) {
                Ok((n, renders)) => {
                    println!("PASS: server conformance (deployable): {} \
                              cases byte-exact ({} render-31 responses)",
                             n, renders);
                    ExitCode::SUCCESS
                }
                Err(reason) => {
                    println!("FAIL: conformance: {}", reason);
                    ExitCode::FAILURE
                }
            }
        }
        "--handle" => {
            let path = match args.get(2) {
                Some(p) => p.clone(),
                None => {
                    eprintln!("usage: xr-updateserver --handle <file>");
                    return ExitCode::from(2);
                }
            };
            let raw = match std::fs::read(&path) {
                Ok(r) => r,
                Err(e) => {
                    eprintln!("FAIL: {}: {}", path, e);
                    return ExitCode::FAILURE;
                }
            };
            let spec = spec_value("base").expect("spec base");
            let (status, out) = handle(&raw, &spec, None);
            print!("{}", out);
            if status == 200 {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            }
        }
        _ => {
            eprintln!("usage: xr-updateserver --self-check | \
                       --conformance <file> | --handle <file>");
            ExitCode::from(2)
        }
    }
}

fn run_conformance(path: &str) -> Result<(usize, usize), String> {
    let raw = std::fs::read_to_string(path)
        .map_err(|e| format!("{}: {}", path, e))?;
    let doc = parse_json(&raw).ok_or("corpus not parseable")?;
    let cases = match get(&doc, "cases") {
        Some(Value::Arr(a)) if !a.is_empty() => a.clone(),
        Some(_) => {
            return Err("zero conformance cases — a runner that runs nothing                         certifies nothing"
                .to_string())
        }
        _ => return Err("corpus has no cases array".to_string()),
    };
    let mut renders = 0usize;
    for (idx, case) in cases.iter().enumerate() {
        let id = as_str(get(case, "id").unwrap_or(&Value::Null))
            .unwrap_or("?")
            .to_string();
        let bail = |what: String, id: &str, idx: usize| -> String {
            format!("case {} ({}): {}", id, idx, what)
        };
        let frame = as_str(get(case, "request").unwrap_or(&Value::Null))
            .ok_or_else(|| bail("no request frame".to_string(), &id, idx))?
            .to_string();
        let cl = match get(case, "content_length") {
            None | Some(Value::Null) => None,
            Some(Value::Num(n)) => n.parse::<usize>().ok(),
            _ => None,
        };
        let variant = as_str(get(case, "spec_variant")
            .unwrap_or(&Value::Null))
            .unwrap_or("base")
            .to_string();
        let spec = spec_value(&variant).ok_or_else(|| {
            bail(format!("unknown spec variant {}", variant), &id, idx)
        })?;
        let want_status = match get(case, "expect_status") {
            Some(Value::Num(n)) => n.parse::<u16>().unwrap_or(0),
            _ => return Err(bail("no expect_status".to_string(), &id, idx)),
        };
        let want_out = as_str(get(case, "expect_response")
            .unwrap_or(&Value::Null))
            .unwrap_or("")
            .to_string();
        let (status, out) = handle(frame.as_bytes(), &spec, cl);
        if status != want_status || out != want_out {
            return Err(bail(
                format!(
                    "divergence (status {} vs {}, bytes {} vs {})",
                    status,
                    want_status,
                    out.len(),
                    want_out.len()
                ),
                &id,
                idx,
            ));
        }
        if handle(frame.as_bytes(), &spec, cl) != (status, out.clone()) {
            return Err(bail(
                "stateful (second handle differs)".to_string(),
                &id,
                idx,
            ));
        }
        if status == 200 {
            renders += 1;
        }
    }
    Ok((cases.len(), renders))
}
