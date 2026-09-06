# VL iOS Certification

## Status

This track certifies the Flutter mobile builder's iOS simulator capability independently from Android certification.

## Baseline certification scope

The baseline workflow proves that, on an exact source SHA:

1. Flutter 3.38.1 is available on a macOS runner.
2. A trusted Flutter iOS fixture analyzes successfully.
3. An unsigned iOS Simulator `Runner.app` builds with `--no-codesign`.
4. The app installs and launches on an iOS Simulator.
5. The simulator artifact is hashed and uploaded as immutable CI evidence.
6. No Apple signing, provisioning, App Store, TestFlight, or production credentials are used.

A passing baseline allows only this claim:

> iOS simulator build capability verified.

It does **not** allow these claims:

- iOS device signing certified;
- TestFlight certified;
- App Store release certified;
- production iOS deployment certified.

## Graduation gates

Before VL may claim production-grade iOS delivery, a separate controlled graduation must prove:

- governed Apple Developer identity and credential storage;
- signing certificate and provisioning-profile lifecycle controls;
- physical-device or governed device-cloud validation;
- signed archive/export evidence;
- TestFlight release evidence where explicitly authorized;
- rollback/revocation procedure;
- human approval before any external distribution;
- no ambient Apple credentials available to generated code.

Those graduation gates must remain separate from the baseline simulator certification.
