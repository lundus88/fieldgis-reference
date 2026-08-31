# VL Voice Input V1

Status: Experimental / P1-high

## Goal
Add voice as a third software-request input beside text and PRD while preserving the existing VL Spec Compiler, builder routing, validation, certification, and human production approval controls.

## V1 flow

Voice capture -> Speech-to-text -> Transcript review -> Explicit user confirmation -> Existing software request/spec intake -> App Spec -> Compiler -> Validation -> Builder routing -> Factory staging run -> QA -> Certification -> Human approval -> Production promotion.

## Hard rules

1. Voice is an input adapter only. It is not a release or deployment authority.
2. A transcript must be visible and editable before submission.
3. Explicit confirmation is required before a voice-derived request may enter spec intake.
4. Empty, failed, or unconfirmed transcripts fail closed.
5. Voice input must never call production promotion directly.
6. Voice input must never alter, remove, satisfy, or bypass release gates.
7. The existing `human-approval` terminal gate remains mandatory.
8. Source provenance must be retained as `voice` when the request is normalized.

## Phase plan

### V1
- Microphone capture in VL UI.
- Speech-to-text.
- Transcript preview/edit.
- Language metadata where available.
- Explicit confirmation.
- Submit confirmed transcript to the existing spec-intake path.

### V2
- Clarifying questions when requirements are incomplete.
- Optional text-to-speech responses.

### V3
- Conversational AI Project Director / Factory Control, still governed by existing release gates.

## Acceptance criteria

- Voice contract validates in CI.
- CI proves direct factory execution and direct production execution are prohibited by contract.
- CI proves `human-approval` remains the terminal step of the PRD compiler smoke test.
- No service-role or secret credentials are exposed in public clients.
- Unsupported browser/device microphone capability degrades safely to text input.
- All required branch-protection checks must pass on the current PR head before merge.

## Runtime integration note

The current production compiler endpoint is read-only/production-locked and compiles persisted `app_specs`. Voice V1 therefore belongs before App Spec persistence, not inside the compiler and not in production promotion.
