# patchinfo — <id>

<!-- All fields below are MANDATORY (linted by `xr-patch lint`, P2-T3; extended
     by P3-T6). Replace the placeholders. Delete this comment in the real file. -->

- **id:** <patch id, e.g. 0001-brand-ui — must match manifest `id`>
- **title:** <one-line what the patch does>
- **owner:** <owning team/handle, e.g. @xr/platform>
- **category:** <one of branding|hook_points|blink_seams|content_seams|network_seams|ui|extension_chokepoint>
- **files:** <upstream files this patch touches (paths relative to src/)>
- **upstream-bug-if-any:** <crbug.com/… link, or "none">
- **retirement plan:** <how this patch dies: upstreamed / superseded by //xr override / obsolete at milestone N>
- **rebase-notes:** <anything the P3 rebase bot or a human rebaser must know>

## Why this patch exists

<one paragraph: the feature/requirement and why a patch is the chosen
mechanism (Plan §1.2 intake order: components before patches).>

## Upstream drift risk

<what upstream changes would conflict with this patch, and how to detect them.>
