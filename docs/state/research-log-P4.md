# Research log — P4 (identity-seam spike)

**Pin:** `d04cdb24d67b081f6cf80200ffc5233f44b61109` (Chromium 152.0.7977.82)
**Method:** every upstream byte came through `build/upstream/fetch.py`
(gitiles `?format=TEXT`), the repo's only network choke point. Files were
fetched once into a scratch tree and grepped locally; each claim below cites
`file:line@pin` and is re-verified by `./scripts/build spike citation-audit`.

**Honesty note:** this phase produces **static** evidence only. No browser was
compiled or run (HG-9 open), so no runtime result is claimed anywhere.

## R1 — The embedder partition override: §1.4's symbol is wrong

* Grepped the fetched `content/public/browser/content_browser_client.h` for
  `StoragePartitionConfig`: one hit, at **line 1208** —
  `virtual StoragePartitionConfig GetStoragePartitionConfigForSite(BrowserContext*, const GURL& site);`
* Grepped the whole fetched set for `ForSiteInstance`: **zero** matches for a
  partition-config symbol. Only `ShouldCompareEffectiveURLsForSiteInstanceSelection`
  and `RenderProcessHostImpl::*ForSiteInstance` (unrelated) exist.
* `chrome/browser/chrome_content_browser_client.h:188` overrides
  `GetStoragePartitionConfigForSite` — so the hook is real and overridden
  upstream; the *name* in §1.4 is not.
* **Conclusion:** §1.4's named API is stale. See ADR-0042 and
  `draft-issue-0002` disposition 1 (accepted: A2 pins evolved symbols).

## R2 — Who calls it, and when

* `content/browser/site_info.cc:819` — the only caller in the fetched set:
  `SiteInfo::GetStoragePartitionConfigForUrl()`.
* `content/browser/site_info.cc:335` —
  `if (!storage_partition_config.has_value()) { … }` — i.e. the embedder
  override is consulted **only when the `UrlInfo` carries no config**.
* `content/browser/site_info.cc:282` — the config is taken from
  `url_info.storage_partition_config` when present.
* **Conclusion:** there are two seams, and the embedder override is the
  fallback. The primary seam is the `UrlInfo` field — which is
  **content-private** (`content/browser/url_info.h` exists; there is no
  `content/public/browser/url_info.h`), so an embedder cannot populate it
  directly.

## R3 — The seam that does work, and it is public

* `content/public/browser/site_instance.h:255` —
  `SiteInstance::CreateForFixedStoragePartition(BrowserContext*, const GURL& url, const StoragePartitionConfig&)`,
  documented at :252-254 as *"create a SiteInstance in a new BrowsingInstance
  with a custom StoragePartition that is preserved across navigations"*.
* `content/browser/site_instance_impl.cc:244-256` — builds
  `UrlInfo(UrlInfoInit(url).WithStoragePartitionConfig(partition_config))` with
  `is_fixed_storage_partition=true`; `CHECK(!partition_config.is_default())`
  at :249.
* `content/browser/site_instance_impl.cc:160-165` — creates a new
  `BrowsingInstance` carrying that flag.
* `content/browser/browsing_instance.h:106-110` — `is_fixed_storage_partition`
  *"indicates whether the current StoragePartition will apply to future
  navigations"*.
* **Conclusion:** this is a supported, public, embedder-reachable seam. No
  `content/**` patch is needed, so §12.7 is satisfied.

## R4 — The invariant is upstream's own, and it is CHECK-enforced

* `content/browser/browsing_instance.cc:178-183` —
  `CHECK_EQ(storage_partition_config_.value(), storage_partition_config)` with
  the comment *"We should only use a single StoragePartition within a
  BrowsingInstance."*
* `content/browser/browsing_instance.cc:263-267` — a `UrlInfo` without a
  config inherits the BrowsingInstance's config.
* `content/browser/renderer_host/render_process_host_impl.cc:4947-4955` —
  reuse requires `host->InSameStoragePartition(dest_partition)`.
* `content/browser/renderer_host/render_process_host_impl.h:197-200` —
  *"A RenderProcessHost is also associated with one and only one
  StoragePartition. This allows us to implement strong storage isolation …"*
* **Caveat:** §1.4's quoted sentence ("two documents from different profiles
  or StoragePartitions can never share the same renderer process") is **not**
  the current upstream wording. The property holds; the sentence is stale.

## R5 — Per-partition network state

* `content/browser/storage_partition_impl.cc:3506` — `InitNetworkContext()`
  calls `ConfigureNetworkContextParams(browser_context, is_in_memory(),
  relative_partition_path, …)` **per partition**: the embedder hook for
  per-identity proxy/DNS.
* `services/network/public/mojom/network_context.mojom` — per-`NetworkContext`:
  `initial_proxy_config` :443, `initial_custom_proxy_config` :450,
  `custom_proxy_config_client_receiver` :451,
  `transport_security_persister_file_name` :307 (HSTS),
  `http_cache_directory` :242, `cookie_database_name` :282,
  `http_server_properties_file_name` :302.
* **DNS is QUALIFIED.** `services/network/network_context.cc:2234` uses
  `url_request_context_->host_resolver()` (per context), but
  `services/network/network_service.cc:492` constructs **one**
  `HostResolverManager` per NetworkService, and
  `network_context.cc:2244-2254` shows a standalone resolver is only created
  for config overrides (and with caching *disabled*). The OS resolver cache is
  outside the browser. §1.4.5's "context-local" claim is too strong.

## R6 — Ephemeral / OTR

* `content/browser/storage_partition_impl.cc:3378-3384` —
  `GetStoragePartitionPath()` returns `std::nullopt` when `is_in_memory()`.
* `content/browser/browser_context.cc:148` —
  `CHECK(storage_partition_config.in_memory())` when `IsOffTheRecord()`.
* `chrome/browser/profiles/profile.h:274` — `GetOriginalProfile()`.
* **Conclusion:** OTR and custom partition domains coexist, but OTR forces
  in-memory. Fortress works and is disk-free by construction.

## R7 — Config identity and the empty-domain trap

* `content/public/browser/storage_partition_config.h:44` —
  `Create(browser_context, partition_domain, partition_name, in_memory)`.
* `:37` — *"partition_domain … must NOT be an empty string"*; `:57` —
  `is_default()` is `partition_domain_.empty()`.
* **Consequence:** an empty domain silently means "the default partition".
  That is a fail-open trap an identity implementation must reject, not fall
  through.

## R8 — Where a tab's partition is decided

* `chrome/browser/ui/navigator/browser_navigator.cc:479-504` —
  `CreateTargetContents()` builds `initial_site_instance_for_new_contents`
  and calls `WebContents::Create(create_params)`. This is the correct, and
  the earliest, embedder-side point at which "which identity is this tab?"
  is answerable — before the WebContents exists.
* **This dissolves §1.4's #1 risk**: a `WebContentsUserData` consulted during
  partition selection would race the first navigation; taking the seam at
  creation makes the question moot.

## R9 — Hosted CI root causes (debt D-A)

* `api.github.com/repos/ahmadrrrtx/xr-core` → **404**. Both workflows cloned
  it. The org repo `RRRTX-Labs/xr-core` exists and is public.
* `packages.ubuntu.com/noble/minisign` → package exists (0.11-1, universe);
  absent on a bare machine and on GitHub-hosted runners by default.
* `actions/runner#4001` — the platform misfire that produced the spurious
  push-triggered nightly run (0 jobs, `created_at == updated_at`).

## UNVERIFIED (deliberately not claimed)

* Runtime behaviour of any of the above — **PENDING-FARM (HG-21)**.
* TLS/QUIC session-cache scoping: inferred per-`URLRequestContext` but not
  located at a citable line, so it is **not** in the measured table.
* Storage-key plumbing for BroadcastChannel / SharedWorker / `window.name`
  (`blink::StorageKey`): not fetched this phase; recorded as a census gap
  rather than guessed.
* Upstream corpus probes (`site_isolation_browsertest.cc`,
  `process_reuse_browsertest.cc`) and Brave's container implementation: not
  fetched — the primary seam turned out to be public API, so prior-art
  archaeology was not on the critical path. **Recorded as a gap.**
* Chrome 152-era advisories touching site isolation: not queried this phase.
  **Recorded as a gap**; promotion is HG territory.
