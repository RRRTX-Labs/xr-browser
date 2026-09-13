// Copyright 2026 RRRTX Labs
// Use of this source code is governed by the MPL-2.0 license that can be
// found in the LICENSE file.
//
// Intent: S0-bench — the P11-T7 shield decision/apply microbenchmark
// (build/qa/perf/shield_bench.{py,cc}; the .py driver compiles and runs
// this file, merges its rows into docs/state/bench-trend.json and adds
// the Python-fake-binding rows). Methodology (policy/bench precedent):
// steady_clock, warmup excluded, >=50k measured decisions over a
// deterministic synthetic corpus (NO RNG, NO wall clock in the data —
// the brief's determinism law), p50/p99/p99.9 reported, -O2 (the driver
// records the exact flags; no LTO games). Results are MEASURED numbers
// with hardware caveats — this binary prints NO verdicts (perf_gate
// owns verdicts; rig-class law: sandbox = trend). Rows are emitted in
// the normalized perf_gate shape; rss_structures_mb has no budget row
// and is RECORD-ONLY there (the <=80MB plan budget is a browser-side
// reference-class claim — farm lane, docs/qa/browser-harness.md).
//
// Engine bindings: --engine fake (default) binds shield/core's
// TableEngine (the deterministic std-only engine the Python fake mirrors
// byte-for-byte); --engine real binds the vendored adblock-rust through
// the shield/engine FFI shim and is ONLY compilable with
// -DXR_SHIELD_REAL_ENGINE against a cargo-built libxr_shield_engine
// (hosted lane; never claimed where cargo is absent).
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <vector>

#include "common/core/json.h"
#include "shield/core/apply.h"
#include "shield/core/bundle.h"
#include "shield/core/context.h"
#include "shield/core/engine.h"
#include "shield/core/fake_engine.h"
#include "shield/core/match.h"
#include "shield/core/posture.h"
#include "shield/core/scope.h"

#ifdef XR_SHIELD_REAL_ENGINE
#include "shield/engine/xr_shield_engine.h"
#endif

using namespace xr::shield;
using Clock = std::chrono::steady_clock;

namespace {

struct Sample {
  double p50, p99, p999;
};

Sample Percentiles(std::vector<double>& v) {
  std::sort(v.begin(), v.end());
  auto at = [&](double q) {
    return v[static_cast<size_t>(q * static_cast<double>(v.size() - 1))];
  };
  return Sample{at(0.50), at(0.99), at(0.999)};
}

double RssMb() {
#ifdef __linux__
  std::FILE* f = std::fopen("/proc/self/status", "r");
  if (!f) return -1.0;
  char line[256];
  double mb = -1.0;
  while (std::fgets(line, sizeof(line), f)) {
    long long kb = 0;
    if (std::sscanf(line, "VmRSS: %lld kB", &kb) == 1) {
      mb = static_cast<double>(kb) / 1024.0;
      break;
    }
  }
  std::fclose(f);
  return mb;
#else
  return -1.0;  // honest absence; the driver drops the row
#endif
}

// The deterministic synthetic bundle: 4 lists x per_list rules, five
// rule classes cycling by index (host-block, path-block, wildcard,
// allow-exception, domains-option block) — every shape the b-load
// fixture pins, at volume. g is the global rule number.
std::string MakeBundleDoc(long long version, int per_list) {
  std::string doc = "{\"bundle_version\":" + std::to_string(version) +
                    ",\"lists\":[";
  for (int l = 0; l < 4; ++l) {
    if (l) doc += ",";
    doc += "{\"attribution\":\"The EasyList authors (https://easylist.to/)\","
           "\"name\":\"l" +
           std::to_string(l) + "\",\"rules\":[";
    for (int i = 0; i < per_list; ++i) {
      const long long g = static_cast<long long>(l) * per_list + i;
      if (i) doc += ",";
      const std::string id = "\"id\":\"r" + std::to_string(g) + "\"";
      switch (i % 5) {
        case 0:
          doc += "{\"action\":\"block\",\"filter\":\"||b" +
                 std::to_string(g) + ".track.example^\"," + id +
                 ",\"kind\":\"network\"}";
          break;
        case 1:
          doc += "{\"action\":\"block\",\"filter\":\"||cdn" +
                 std::to_string(g) + ".cdn.example/js/adframe.js\"," + id +
                 ",\"kind\":\"network\"}";
          break;
        case 2:
          doc += "{\"action\":\"block\",\"filter\":\"||wild" +
                 std::to_string(g) + ".wild.example/ad_*.js\"," + id +
                 ",\"kind\":\"network\"}";
          break;
        case 3:
          doc += "{\"action\":\"allow\",\"filter\":\"||allow" +
                 std::to_string(g) + ".allow.example^\"," + id +
                 ",\"kind\":\"network\"}";
          break;
        default:
          doc += "{\"action\":\"block\",\"domains\":[\"site" +
                 std::to_string(g % 97) +
                 ".example\"],\"filter\":\"||meta" + std::to_string(g) +
                 ".meta.example^\"," + id + ",\"kind\":\"network\"}";
          break;
      }
    }
    doc += "]}";
  }
  doc += "],\"name\":\"xr-bench\",\"refusals\":[],\"schema\":\"xr-list-"
         "bundle\",\"schema_version\":1}";
  return doc;
}

// The deterministic request mix (20 classes): 70% no-match, 15% host
// block, 5% path block, 5% wildcard block, ~5% allow-exception. g is
// chosen with a fixed coprime step so every rule class gets exercised.
// g is aligned to the rule class the request targets (rule classes cycle
// by g%5 in MakeBundleDoc): host-block g%5==0, path-block ==1, wildcard
// ==2, allow ==3 — an unaligned g would silently measure no-match scans
// for "matching" requests (the mix counter would expose it, but the
// alignment makes the corpus what it claims to be). REAL-ENGINE lane:
// the allow class reports no-opinion there (ABP checks exceptions only
// after a block match — provenance divergence D-5; the paired-exception
// path rides the parity corpus, not the bench mix).
std::string MakeContextJson(long long j, int nrules) {
  const long long base = (j * 7919) % (nrules / 5);
  const char* classes[6] = {"kSubresource", "kScript",     "kNavigation",
                            "kNetwork",     "kPermission", "kStorage"};
  std::string url;
  switch (j % 20) {
    case 14:
    case 15:
    case 16:
      url = "https://b" + std::to_string(base * 5) +
            ".track.example/x" + std::to_string(j) + ".js";
      break;
    case 17:
      url = "https://cdn" + std::to_string(base * 5 + 1) +
            ".cdn.example/js/adframe.js";
      break;
    case 18:
      url = "https://allow" + std::to_string(base * 5 + 3) +
            ".allow.example/x";
      break;
    case 19:
      url = "https://wild" + std::to_string(base * 5 + 2) +
            ".wild.example/ad_9.js";
      break;
    default:
      url = "https://nm" + std::to_string(j) + ".clean.example/res/" +
            std::to_string(j) + ".js";
      break;
  }
  // registrable_domain = the naive last-two-labels of the url host (all
  // bench hosts are RFC 2606 .example — fixture data, never fetched)
  const size_t hs = url.find("://") + 3;
  const size_t he = url.find('/', hs);
  const std::string host = url.substr(hs, he - hs);
  const size_t d1 = host.rfind('.');
  const size_t d0 = host.rfind('.', d1 - 1);
  const std::string rd = host.substr(d0 + 1);
  return std::string("{\"identity\":{\"value\":\"xr:00000000-0000-4000-"
                     "8000-000000000001\"},\"origin\":{\"registrable_domain\":")
      + "\"" + rd + "\",\"scheme\":\"https\"},\"request_class\":\"" +
      classes[j % 6] + "\",\"url\":\"" + url + "\"}";
}

bool ParseDoc(const std::string& doc, xr::common::JsonValue* out) {
  xr::common::JsonParseResult parsed = xr::common::ParseJson(doc);
  if (!parsed.ok) return false;
  *out = parsed.value;
  return true;
}

#ifdef XR_SHIELD_REAL_ENGINE
// The real-engine binding: adblock-rust behind the SAME BlockingEngine
// interface (engine.h) through the shield/engine FFI shim. rule_id/
// list_id are recovered from the normalized bundle via the hit's
// list/rule indices (the shim borrows, never copies, strings).
class RealEngine : public BlockingEngine {
 public:
  RealEngine(const std::string& bundle_doc, const NormalizedBundle* bundle,
             std::string* err)
      : bundle_(bundle) {
    const char* detail = nullptr;
    engine_ = xr_shield_engine_create(bundle_doc.c_str(), &detail);
    if (engine_ == nullptr) {
      *err = detail != nullptr ? detail : "engine-create-failed";
    }
  }
  ~RealEngine() override { xr_shield_engine_free(engine_); }
  bool alive() const override {
    return engine_ != nullptr && xr_shield_engine_alive(engine_) != 0;
  }
  bool Match(const RequestContext& ctx, EngineHit* hit) override {
    if (engine_ == nullptr) return false;
    const std::string match_url =
        ctx.parts.scheme + "://" + ctx.parts.host + ctx.parts.path;
    XrShieldHit h{};
    if (xr_shield_engine_match(engine_, match_url.c_str(),
                               ctx.parts.host.c_str(), ctx.parts.path.c_str(),
                               ctx.origin.registrable_domain.c_str(),
                               &h) != 1) {
      return false;
    }
    hit->action = static_cast<Action>(h.action);
    if (h.list_index < bundle_->lists.size() &&
        h.rule_index < bundle_->lists[h.list_index].rules.size()) {
      hit->list_id = bundle_->lists[h.list_index].name;
      hit->rule_id = bundle_->lists[h.list_index].rules[h.rule_index].id;
    }
    if (h.redirect_resource != nullptr) hit->redirect_resource =
        h.redirect_resource;
    return true;
  }

 private:
  XrShieldEngine* engine_ = nullptr;
  const NormalizedBundle* bundle_;
};
#endif

void Usage() {
  std::fprintf(stderr,
               "usage: shield_bench [--iters N>=50000] [--rules N>=4000, "
               "%%4==0] [--apply-iters N>=3] [--rig trend|reference] "
               "[--engine fake|real]\n");
}

}  // namespace

int main(int argc, char** argv) {
  long long iters = 50000, rules = 20000, apply_iters = 10;
  std::string rig = "trend", engine_kind = "fake";
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    auto next = [&](long long* v) {
      if (i + 1 >= argc) { Usage(); std::exit(2); }
      *v = std::atoll(argv[++i]);
    };
    if (a == "--iters") next(&iters);
    else if (a == "--rules") next(&rules);
    else if (a == "--apply-iters") next(&apply_iters);
    else if (a == "--rig" && i + 1 < argc) rig = argv[++i];
    else if (a == "--engine" && i + 1 < argc) engine_kind = argv[++i];
    else { Usage(); return 2; }
  }
  if (iters < 50000 || rules < 4000 || rules % 4 != 0 || apply_iters < 3 ||
      (rig != "trend" && rig != "reference") ||
      (engine_kind != "fake" && engine_kind != "real")) {
    Usage();
    return 2;
  }
#ifndef XR_SHIELD_REAL_ENGINE
  if (engine_kind == "real") {
    std::fprintf(stderr,
                 "usage error: --engine real needs -DXR_SHIELD_REAL_ENGINE "
                 "+ the cargo-built shim (hosted lane only)\n");
    return 2;
  }
#endif

  const int per_list = static_cast<int>(rules / 4);
  const double rss_base = RssMb();

  // ---- the bundle (built once; the decision loop consumes it) ----
  const std::string doc = MakeBundleDoc(3, per_list);
  xr::common::JsonValue raw;
  if (!ParseDoc(doc, &raw)) {
    std::fprintf(stderr, "FAIL: synthetic bundle doc did not parse\n");
    return 1;
  }
  NormalizedBundle bundle;
  std::string detail;
  if (ParseBundle(raw, &bundle, &detail) != BundleResult::kOk) {
    std::fprintf(stderr, "FAIL: ParseBundle refused: %s\n", detail.c_str());
    return 1;
  }

  // ---- the contexts (parse cost excluded from the decision loop; the
  // product path parses once per request, the budget is the DECISION) ----
  std::vector<RequestContext> ctxs;
  ctxs.reserve(static_cast<size_t>(iters));
  for (long long j = 0; j < iters; ++j) {
    xr::common::JsonValue cj;
    if (!ParseDoc(MakeContextJson(j, static_cast<int>(rules)), &cj)) {
      std::fprintf(stderr, "FAIL: context %lld did not parse\n", j);
      return 1;
    }
    RequestContext ctx;
    if (ParseRequestContext(cj, &ctx, &detail) != ParseResult::kOk) {
      std::fprintf(stderr, "FAIL: ParseRequestContext %lld: %s\n", j,
                   detail.c_str());
      return 1;
    }
    ctxs.push_back(std::move(ctx));
  }

  // ---- one exception scope (the scope layer participates) ----
  ScopeSet scopes;
  {
    xr::common::JsonValue sj;
    if (!ParseDoc("{\"scopes\":[{\"reason\":\"user-allow\",\"scope_id\":"
                  "\"ex-1\",\"site\":\"example.org\"}]}", &sj) ||
        ParseScopeSet(sj, &scopes, &detail) != ScopeResult::kOk) {
      std::fprintf(stderr, "FAIL: scope set: %s\n", detail.c_str());
      return 1;
    }
  }

  // ---- the engine binding ----
  std::unique_ptr<BlockingEngine> engine;
#ifdef XR_SHIELD_REAL_ENGINE
  if (engine_kind == "real") {
    std::string err;
    engine.reset(new RealEngine(doc, &bundle, &err));
    if (!engine->alive()) {
      std::fprintf(stderr, "FAIL: real engine create: %s\n", err.c_str());
      return 1;
    }
  }
#endif
  if (!engine) engine.reset(new TableEngine(&bundle));

  const PostureInputs posture_in{};  // normal/green: the decision path
  const double rss_structures =
      (RssMb() < 0.0 || rss_base < 0.0) ? -1.0 : RssMb() - rss_base;

  // ---- warmup (excluded), then the measured decision loop ----
  long long counts[3] = {0, 0, 0};  // block-ish, allow-ish, no-match
  auto classify = [&](const MatchOutcome& o) {
    if (o.verdict.engine_decision &&
        ActionName(o.verdict.action) == std::string("block")) counts[0]++;
    else if (o.verdict.engine_decision) counts[1]++;
    else counts[2]++;
  };
  for (long long j = 0; j < 5000; ++j) {
    DecideMatch(ctxs[static_cast<size_t>(j % iters)], &bundle, engine.get(),
                scopes, 1000 + j, posture_in);
  }
  std::vector<double> dec(static_cast<size_t>(iters));
  for (long long j = 0; j < iters; ++j) {
    const auto t0 = Clock::now();
    const MatchOutcome o = DecideMatch(
        ctxs[static_cast<size_t>(j)], &bundle, engine.get(), scopes,
        1000 + j, posture_in);
    const auto t1 = Clock::now();
    dec[static_cast<size_t>(j)] =
        std::chrono::duration<double, std::milli>(t1 - t0).count();
    classify(o);
  }
  const Sample ds = Percentiles(dec);

  // ---- the apply path: bytes -> parse -> digest -> activate, a chained
  // monotonic sequence (bundle_version climbs; pins keep the last two) --
  std::vector<double> app(static_cast<size_t>(apply_iters));
  ApplyState state{};
  for (long long it = 0; it < apply_iters; ++it) {
    const std::string adoc = MakeBundleDoc(100 + it, per_list);
    const auto t0 = Clock::now();
    xr::common::JsonValue araw;
    NormalizedBundle cand;
    ApplyState out;
    std::string adetail;
    const bool ok =
        ParseDoc(adoc, &araw) &&
        ParseBundle(araw, &cand, &adetail) == BundleResult::kOk &&
        ApplyBundle(cand, state, 2000 + it * 10, &out, &adetail) ==
            ApplyResult::kOk;
    const auto t1 = Clock::now();
    if (!ok) {
      std::fprintf(stderr, "FAIL: apply iter %lld: %s\n", it,
                   adetail.c_str());
      return 1;
    }
    state = out;
    app[static_cast<size_t>(it)] =
        std::chrono::duration<double, std::milli>(t1 - t0).count();
  }
  std::vector<double> app_sorted = app;
  const Sample as = Percentiles(app_sorted);
  const double worst_apply = *std::max_element(app.begin(), app.end());

  // ---- human table (numbers ONLY — perf_gate owns verdicts) ----
  std::printf("shield-bench (%s engine, %s rig): %lld decisions over %lld "
              "rules\n", engine_kind.c_str(), rig.c_str(), iters, rules);
  std::printf("  decision ms: p50=%.6f p99=%.6f p99.9=%.6f (mix: %lld "
              "block / %lld allow / %lld no-match)\n",
              ds.p50, ds.p99, ds.p999, counts[0], counts[1], counts[2]);
  std::printf("  apply ms (%lld-rule bundle, %lld iters): median=%.3f "
              "worst=%.3f\n", rules, apply_iters, as.p50, worst_apply);
  if (rss_structures >= 0.0)
    std::printf("  rss structures delta: %.3f MB (record-only)\n",
                rss_structures);
  std::printf("  verdicts: tools/perf_gate.py (rig-class law)\n");

  // ---- canonical JSON line (the normalized perf_gate shape) ----
  // Metric naming is engine-dependent BY LAW: the product budget row
  // (filter_decision_p99_ms) may only be fed by the REAL engine (the
  // hosted reference rig); the deterministic table engine's pipeline
  // number is fakecore_decision_p99_ms — RECORD-ONLY in perf_gate (no
  // budget row), because the sandbox fake is not the product engine.
  const char* dec_metric = engine_kind == "real" ? "filter_decision_p99_ms"
                                                 : "fakecore_decision_p99_ms";
  std::printf("{\"engine\":\"%s\",\"iters\":%lld,\"name\":\"shield-bench\","
              "\"rig_class\":\"%s\",\"rows\":[",
              engine_kind.c_str(), iters, rig.c_str());
  std::printf("{\"metric\":\"%s\",\"n\":%lld,\"p50\":%.6f,"
              "\"p99\":%.6f,\"p999\":%.6f,\"unit\":\"ms\",\"value_us\":%.6f}",
              dec_metric, iters, ds.p50, ds.p99, ds.p999, ds.p99);
  std::printf(",{\"metric\":\"list_apply_ms\",\"n\":%lld,\"p50\":%.3f,"
              "\"p99\":%.3f,\"unit\":\"ms\",\"value_us\":%.3f,"
              "\"worst_single_ms\":%.3f}",
              apply_iters, as.p50, as.p99, worst_apply, worst_apply);
  if (rss_structures >= 0.0)
    std::printf(",{\"metric\":\"rss_structures_mb\",\"unit\":\"MB\","
                "\"value_us\":%.3f}", rss_structures);
  std::printf("],\"rules\":%lld}\n", rules);
  return 0;
}
