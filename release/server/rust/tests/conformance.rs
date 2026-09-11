//! Integration test: replays the committed conformance corpus against the
//! deployable (`cargo test` on the hosted runner). A byte of divergence
//! from the reference (which generated the corpus) is a red gate — the
//! P9 differential-parity lesson applied to the language boundary.
#![forbid(unsafe_code)]

use xr_updateserver::{as_str, canonical, get, handle, parse_json,
                     spec_value, stub_sig, Value, PREFIX};

#[test]
fn conformance_corpus_is_byte_exact() {
    let raw = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../tests/conformance.json"
    ))
    .expect("corpus present");
    let doc = parse_json(&raw).expect("corpus parseable");
    let cases = match get(&doc, "cases") {
        Some(Value::Arr(a)) => a.clone(),
        _ => panic!("corpus has no cases array"),
    };
    assert!(
        cases.len() >= 40,
        "conformance corpus must carry >= 40 cases (got {})",
        cases.len()
    );
    let mut renders = 0usize;
    for case in &cases {
        let id = as_str(get(case, "id").unwrap_or(&Value::Null))
            .unwrap_or("?")
            .to_string();
        let frame = as_str(get(case, "request").unwrap_or(&Value::Null))
            .unwrap_or("")
            .to_string();
        let cl = match get(case, "content_length") {
            None | Some(Value::Null) => None,
            Some(Value::Num(n)) => n.parse::<usize>().ok(),
            _ => None,
        };
        let variant =
            as_str(get(case, "spec_variant").unwrap_or(&Value::Null))
                .unwrap_or("base")
                .to_string();
        let spec = spec_value(&variant)
            .unwrap_or_else(|| panic!("unknown spec variant {}", variant));
        let want_status = match get(case, "expect_status") {
            Some(Value::Num(n)) => n.parse::<u16>().unwrap_or(0),
            _ => panic!("{}: no expect_status", id),
        };
        let want_out =
            as_str(get(case, "expect_response").unwrap_or(&Value::Null))
                .unwrap_or("")
                .to_string();
        let (status, out) = handle(frame.as_bytes(), &spec, cl);
        assert_eq!(
            (status, out.clone()),
            (want_status, want_out),
            "case {}: bytes diverge from the reference",
            id
        );
        // statelessness law: the same request, twice, identical bytes
        assert_eq!(
            handle(frame.as_bytes(), &spec, cl),
            (status, out.clone()),
            "case {}: stateful server detected",
            id
        );
        if status == 200 {
            renders += 1;
            assert!(out.starts_with(PREFIX) && out.ends_with('\n'));
            let env = parse_json(out[PREFIX.len()..].trim_end())
                .expect("200 re-parseable");
            assert_eq!(
                canonical(&env) + "\n",
                out[PREFIX.len()..],
                "case {}: response not canonical",
                id
            );
            let key_id = as_str(
                get(get(&env, "signature").unwrap_or(&Value::Null),
                    "key_id")
                    .unwrap_or(&Value::Null),
            )
            .unwrap_or("");
            let response = get(&env, "response").expect("response object");
            let sig = as_str(
                get(get(&env, "signature").unwrap_or(&Value::Null), "sig")
                    .unwrap_or(&Value::Null),
            )
            .unwrap_or("");
            assert_eq!(
                sig,
                stub_sig(
                    xr_updateserver::KEY_MATERIAL
                        .iter()
                        .find(|(k, _)| *k == key_id)
                        .map(|(_, m)| *m)
                        .expect("pinned key material"),
                    &canonical(response)
                ),
                "case {}: manifest signature not stub-valid (the fuzz \
                 oracle law: nothing renders without a valid signature)",
                id
            );
            assert!(out.len() <= 2048, "case {}: response > 2048", id);
        }
    }
    assert!(renders > 0, "no render-31 responses exercised");
}
