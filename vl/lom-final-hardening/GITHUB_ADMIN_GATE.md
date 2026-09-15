# LOM Final Hardening — GitHub Administrative Gate

Status: BLOCKED_ADMIN until verified live.
Issue: #252.

This repository-side hardening cannot itself modify repository rulesets because the connected GitHub App does not expose repository-administration writes. Therefore the following settings MUST be applied and then independently re-read from GitHub before this program can claim the protected-main enforcement gap is closed.

## Required default-branch ruleset settings

For the effective ruleset protecting the default branch (`main`):

1. Pull request required.
2. Required approving review count: **at least 1**.
3. No bypass actor for normal merge flow.
4. Strict required status checks enabled.
5. Required status checks must include:
   - `governance-policy`
   - `master-compliance`
   - `level6-exact-main-regression`
6. Branch deletion prevented.
7. Non-fast-forward updates prevented.
8. Human approval must remain separate from automated validation; LOM may prepare evidence but may not self-approve.

## Verification rule

Do not mark this gate PASS from documentation or intent. Re-read the live GitHub ruleset and verify the effective values. If review count is 0, any required check is absent, or a bypass actor can circumvent the gate, status remains `BLOCKED_ADMIN` / `HOLD`.

## Authority boundary

- autonomous ceiling: PREPARE_PR
- protected-main merge: HUMAN_ONLY
- production authority: HUMAN_ONLY
- self approval: FORBIDDEN
- production execution: DISABLED by this program
