# Measured shared-state table — what an identity partition does and does not isolate

**Pin:** Chromium `d04cdb24d67b081f6cf80200ffc5233f44b61109` (152.0.7977.82)
**Method:** every row below was measured by fetching the cited file at the pin
through `build/upstream/fetch.py` and locating the quoted text. Rows are
machine-re-checked by `./scripts/build spike citation-audit`, which re-fetches
each cited file and fails if a quote is missing or moved (drift ⇒ CI red).

**Runtime confirmation is `PENDING-FARM` on every row.** Nothing here was
observed by running a browser; a compiled browser does not exist yet (HG-9),
so execution is HG-21. A row that claims a runtime result is a bug in this
document and the audit rejects it.

| id | state | claimed scope (Plan §1.4) | measured scope (at the pin) | what this means | evidence (`file:line@pin`) | quoted source text | runtime |
|----|-------|---------------------------|------------------------------|-----------------|------------------------------|--------------------|---------|
| S-01 | **Embedder partition override** | `ChromeContentBrowserClient::GetStoragePartitionConfigForSiteInstance` resolves identity per `WebContents` | Symbol **does not exist**. The hook is `ContentBrowserClient::GetStoragePartitionConfigForSite(BrowserContext*, const GURL&)`, consulted only when the `UrlInfo` carries no config | §1.4's named API is wrong **and** unusable for identity: it is keyed on `(profile, site)`, so two identities on one site are indistinguishable | `content/public/browser/content_browser_client.h:1208` | `virtual StoragePartitionConfig GetStoragePartitionConfigForSite(` | PENDING-FARM |
| S-02 | **Where the override is consulted** | at SiteInstance creation/association | `SiteInfo::GetStoragePartitionConfigForUrl()`, called from `SiteInfo::Create()` only when the `UrlInfo` has no partition config | Confirms the override is a *fallback*, not the primary seam | `content/browser/site_info.cc:819` | `return GetContentClient()->browser()->GetStoragePartitionConfigForSite(` | PENDING-FARM |
| S-03 | **The seam that does work** | (not named in §1.4) | `SiteInstance::CreateForFixedStoragePartition(profile, url, config)` — public embedder API, *"with a custom StoragePartition that is preserved across navigations"* | This is the identity seam: public, embedder-side, no `content/**` patch needed | `content/public/browser/site_instance.h:255` | `static scoped_refptr<SiteInstance> CreateForFixedStoragePartition(` | PENDING-FARM |
| S-04 | **Non-default requirement** | — | `CHECK(!partition_config.is_default())` in the factory | An identity partition must have a non-empty domain; a default config would be a CHECK crash, not a silent fallback | `content/browser/site_instance_impl.cc:249` | `CHECK(!partition_config.is_default());` | PENDING-FARM |
| S-05 | **Partition is pinned per BrowsingInstance** | identity spans the tab | The first registered SiteInstance fixes the BrowsingInstance's config; a mismatch is `CHECK_EQ`-failed | Cross-site navigations and OOPIFs cannot escape the identity partition | `content/browser/browsing_instance.cc:183` | `CHECK_EQ(storage_partition_config_.value(), storage_partition_config);` | PENDING-FARM |
| S-06 | **Pinning is deliberate, not incidental** | — | *"We should only use a single StoragePartition within a BrowsingInstance."* | Upstream intends the invariant we are borrowing | `content/browser/browsing_instance.cc:179` | `We should only use a single StoragePartition within a BrowsingInstance.` | PENDING-FARM |
| S-07 | **Inheritance to later SiteInstances** | — | A `UrlInfo` without a config inherits the BrowsingInstance's | The partition propagates automatically; we need touch only creation | `content/browser/browsing_instance.cc:263` | `UrlInfo url_info_with_partition =` | PENDING-FARM |
| S-08 | **Renderer non-sharing** | *"two documents from different profiles or StoragePartitions can never share the same renderer process"* | Enforced: reuse requires `InSameStoragePartition()`; upstream's wording is *"A RenderProcessHost is also associated with one and only one StoragePartition"* | §1.4's **property** holds; §1.4's **sentence** is not the current upstream wording | `content/browser/renderer_host/render_process_host_impl.cc:4952` | `if (!host->InSameStoragePartition(dest_partition)) {` | PENDING-FARM |
| S-09 | **One renderer ↔ one partition** | strong storage isolation | *"associated with one and only one StoragePartition … strong storage isolation because all the IPCs … will only ever be able to access the partition they are assigned to"* | The isolation claim is upstream's, not ours | `content/browser/renderer_host/render_process_host_impl.h:197` | `A RenderProcessHost is also associated with one and only one` | PENDING-FARM |
| S-10 | **Per-partition NetworkContext** | each partition gets its own `NetworkContext`, proxy/DNS bound once at creation | `InitNetworkContext()` calls `ConfigureNetworkContextParams(browser_context, is_in_memory, relative_partition_path, …)` **per partition** — the embedder hook for per-identity proxy/DNS | P5's `RouteManager.BindIdentity` has a supported, per-partition creation hook | `content/browser/storage_partition_impl.cc:3506` | `GetContentClient()->browser()->ConfigureNetworkContextParams(` | PENDING-FARM |
| S-11 | **Proxy configuration** | per-partition | `NetworkContextParams::initial_proxy_config` (+ `initial_custom_proxy_config`, `custom_proxy_config_client_receiver`) are **per-NetworkContext** | Distinct SOCKS/DoH per identity is expressible at creation | `services/network/public/mojom/network_context.mojom:443` | `ProxyConfigWithAnnotation? initial_proxy_config;` | PENDING-FARM |
| S-12 | **HSTS state** | per-partition (context-local) | `transport_security_persister_file_name` is a per-`NetworkContext` file (in-memory when unset) | HSTS is context-local — §1.4 correct here | `services/network/public/mojom/network_context.mojom:307` | `mojo_base.mojom.FilePath? transport_security_persister_file_name;` | PENDING-FARM |
| S-13 | **HTTP cache** | per-partition dir; in-memory ⇒ memory-backed | `http_cache_directory` is a per-`NetworkContext` `TransferableDirectory` | Cache is partition-scoped, including the disk path | `services/network/public/mojom/network_context.mojom:242` | `TransferableDirectory? http_cache_directory;` | PENDING-FARM |
| S-14 | **Cookies** | per-partition | `cookie_database_name` is per-`NetworkContext`; in-memory store when empty | Cookie jar is partition-scoped | `services/network/public/mojom/network_context.mojom:282` | `mojo_base.mojom.FilePath? cookie_database_name;` | PENDING-FARM |
| S-15 | **HTTP/QUIC server properties** | — | `http_server_properties_file_name` per-`NetworkContext` | Protocol-support cache (HTTP2/ALT-SVC/QUIC hints) is partition-scoped | `services/network/public/mojom/network_context.mojom:302` | `mojo_base.mojom.FilePath? http_server_properties_file_name;` | PENDING-FARM |
| S-16 | **DNS** | context-local (§1.4.5) | **QUALIFIED.** Each `NetworkContext` uses its own `url_request_context_->host_resolver()`, but the `HostResolverManager` is constructed once per **NetworkService** | The per-context *cache* is partition-local; the manager, its sockets and the OS resolver cache are **shared process-wide**. DNS is a cross-identity correlation surface (see limitations.md) | `services/network/network_context.cc:2234` | `net::HostResolver* internal_resolver = url_request_context_->host_resolver();` | PENDING-FARM |
| S-17 | **DNS manager is shared** | — | `host_resolver_manager_ = std::make_unique<net::HostResolverManager>(…)` in `NetworkService` | Corroborates S-16: one manager for the whole network service | `services/network/network_service.cc:492` | `host_resolver_manager_ = std::make_unique<net::HostResolverManager>(` | PENDING-FARM |
| S-18 | **Off-the-record ⇒ in-memory** | Fortress = OTR `Profile` coexistence | `BrowserContext::GetStoragePartition()` CHECKs `in_memory()` when `IsOffTheRecord()` | OTR and custom partition domains **coexist**, but every OTR partition is forced in-memory. Fortress works; it is also disk-free by construction | `content/browser/browser_context.cc:148` | `CHECK(storage_partition_config.in_memory());` | PENDING-FARM |
| S-19 | **Ephemeral ⇒ no path** | zero bytes on disk | `GetStoragePartitionPath()` returns `std::nullopt` for `is_in_memory()` | No path ⇒ no file can be created; the zero-write claim is measurable by FS-diff | `content/browser/storage_partition_impl.cc:3380` | `if (is_in_memory()) {` | PENDING-FARM |
| S-20 | **Partition path derivation** | — | `StoragePartitionImplMap::GetStoragePartitionPath(domain, name)` builds a per-domain directory | Two identities ⇒ two directories on disk | `content/browser/storage_partition_impl_map.cc:294` | `base::FilePath StoragePartitionImplMap::GetStoragePartitionPath(` | PENDING-FARM |
| S-21 | **Config identity** | domain + name + in_memory | `StoragePartitionConfig::Create(browser_context, partition_domain, partition_name, in_memory)`; equality is defaulted over all fields | The triple is the partition key; our domain must be non-empty | `content/public/browser/storage_partition_config.h:44` | `static StoragePartitionConfig Create(BrowserContext* browser_context,` | PENDING-FARM |
| S-22 | **Domain must be non-empty** | — | *"partition_domain \| must NOT be an empty string"* | An empty domain silently means "the default partition" — a fail-open trap | `content/public/browser/storage_partition_config.h:37` | `be an empty string. Within a domain, partitions can be uniquely identified` | PENDING-FARM |
| S-23 | **Profile ↔ original profile** | Fortress coexists with the normal profile | `Profile::GetOriginalProfile()` returns the recording profile | Identity partitions live under whichever Profile the tab uses; OTR nests | `chrome/browser/profiles/profile.h:274` | `virtual Profile* GetOriginalProfile() = 0;` | PENDING-FARM |

## Profile-shared surfaces (§1.4.5) that a partition does **not** isolate

These are **not** partition-scoped; they are owned by the Profile or the
process. Each is a cross-identity observation surface and each has a
limitations.md entry or a threat-model row.

| id | surface | owner level | why it is shared | consequence for identity |
|----|---------|-------------|------------------|--------------------------|
| P-1 | `HostContentSettingsMap` (site permissions) | Profile | keyed by origin, not partition | granting camera to a site in identity A is visible in identity B |
| P-2 | History / Bookmarks | Profile DB | single DB per Profile | browsing in one identity is recorded in the shared history |
| P-3 | Password store / Autofill | Profile | single encrypted store | credentials are not identity-scoped |
| P-4 | Extension registry | Profile | one registry per Profile | extensions see and can act across identities |
| P-5 | Downloads DB | Profile | single DB | download metadata leaks identity activity |
| P-6 | Favicon cache | Profile-level DB | favicons fetched per origin, cached per Profile | **census row**: a favicon fetch is a network request whose *cache* is shared, so one identity's visit can be inferred from another's cache state |
| P-7 | OS resolver cache / system DNS | OS | outside the browser entirely | see S-16/S-17 |
| P-8 | GPU process | process-global | one GPU process per browser | any GPU-side side channel is cross-identity |
| P-9 | Clipboard | OS/session | system clipboard | copy in one identity, paste in another |

## Audit

```bash
./scripts/build spike citation-audit            # re-fetch + verify every row
```

Writes `evidence/P4/logs/citation-audit.txt`. Exit 1 if any cited file cannot
be fetched, any quote is missing, or any row claims a runtime result.
