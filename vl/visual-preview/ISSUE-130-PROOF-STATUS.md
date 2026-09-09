# Issue #130 — Real Factory Preview Proof Status

Status date: 2026-09-06

## Historical real-artifact proof

The real Factory Runner artifact proof milestone is PASS for one historical PWA factory artifact.

- Factory run: `2e07a4f8-a389-4882-99ac-f800a6179451`
- Builder: `pwa-react-v1`
- Source SHA: `41c105f96f07a227c443d9df05dd95d8acbc188b`
- Factory artifact: `vl-factory-2e07a4f8-a389-4882-99ac-f800a6179451-pwa-react-v1`
- Factory artifact SHA-256: `141b06560f2fe033e2b2fd0fc7217cdf8346950eaa8f3a8e035374d64928d74e`
- App Spec ID: `92287091-4821-42db-9596-c036ec9cd40f`
- App Spec status: `approved`
- App Spec SHA-256 evidence: `e9ae1fba3df7a2e3396639d99c62bd571c67f12160c327de9299cf16a3677bdf`
- Browser verification run: `34026660240`
- Browser verification: PASS
- Desktop screenshot: PASS
- Mobile screenshot: PASS
- Production authority: false

The control-plane record was read-only cross-checked and matched builder key, source SHA, artifact name and artifact SHA-256. Production remained locked.

## Automatic enforcement implementation

Branch `vl/issue-130-visual-preview-evidence` now implements a post-build / pre-callback visual preview gate for eligible `web-react-v1`, `pwa-react-v1`, and `gis-web-v1` Factory builds.

The Factory Runner result is PASS for those builders only when both the immutable build and the independent browser preview gate PASS. Missing/failed preview evidence causes the callback result to fail closed. Preview evidence is uploaded separately with 90-day retention and records source SHA, artifact SHA-256, canonical App Spec SHA-256, desktop/mobile screenshots, console errors, network failures, and `production_authority=false`.

Branch enforcement CI run `34031155298` is PASS. It executed the real preview helper against an immutable Vercel-build-output fixture and separately asserted the Factory Runner fail-closed wiring.

## Enforcement boundary

- `branch_enforcement_implementation = CI_PROVEN`
- `main_enforcement = NOT_ACTIVE`
- `production_enforcement = NOT_ACTIVE`
- `production_authority = false`

No merge or deployment has been performed. A human-reviewed merge to `main`, followed by evidence from a natural eligible Factory Runner build, is required before claiming live Factory-wide enforcement.
