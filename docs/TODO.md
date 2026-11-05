# TODO

Kept current: tick what's done, add what's found.

## Now

- [x] docs/DESIGN.md, agreed with Dan (2026-11-05).
- [x] Port 8794, icon `drama` (Serafina r280).
- [ ] The install on astarte: docs/deploy-astarte.md (Dan's sudo steps), then her config.
- [x] `/security-review` on the branch before the first merge (2026-11-05: nothing exploitable; two hardening notes below).

## Later

- [ ] Parse PDFs in a separate process with no network, so a MuPDF bug can't use the egress the Google Docs fetch needs (security review, 2026-11-05).
- [ ] Narrow the egress to Google's hosts only (an allow-listing proxy), so a LAN device's public IPv6 address isn't reachable either.

- [ ] Voice: hear the cues read aloud, say your line (Serafina has no speech yet).
- [ ] A screenplay PDF's centred names: tested on pasted text, not yet on a real screenplay PDF.
- [ ] Scripts shared between people (a scene partner who's a person).
