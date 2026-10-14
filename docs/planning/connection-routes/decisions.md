# Connection routes: decisions

Model:  Claude Opus 5.5 (the TheConnection architect session)
Status: the record. Each line says who decided and when; open items with a
        default are in `00-index.md` section 11, not here, until Donald
        settles them.
Date:   2026-10-14

| # | Decision | By | Date |
|---|---|---|---|
| D1 | The routing rule: same-account Claude sessions use the native path; Codex, other tools, several Claude accounts and other machines use tc; when unsure, tc. Several accounts on one machine is the headline case. | Donald, through a planning session | 2026-10-14 |
| D2 | Every way Donald works is supported: local sessions with SSH into a dev box, sending to sessions on another box, and (for others) agents on another machine reaching his main computer. | Donald | 2026-10-14 |
| D3 | Codex is reached by the `codex queue` doorbell, not a listener: a listener started inside Codex dies when its command returns (observed in the architect session on 2026-10-14 against Codex 0.160 to 0.162.1; no artifact in the tree yet. CARDS task R4's recorded fixture becomes the artifact). | Donald approved the order; tests run in the architect session | 2026-10-14 |
| D4 | Claude keeps `tc wait` in every account; no outside push into a Claude session is supported. | Donald, through a planning session | 2026-10-14 |
| D5 | The board has two looks, dark and Daylight (a light palette Donald supplied), and a switch between them. Committed as `1791cbf`. | Donald | 2026-10-14 |
| D6 | The work runs as: plan, then lane agents in parallel where the plan allows, then review. Nothing is dispatched until Donald says go. (The ceiling of 3 lanes at once is the architect's default, open for Donald.) | Donald | 2026-10-14 |
