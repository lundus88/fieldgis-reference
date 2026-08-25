# VL Mobile Builder Certification

`mobile-flutter-v1` is a candidate VRS Labs Android Mobile Builder.

## Activation rule

No certification approval -> no activation.

The builder must remain `experimental` until all required gates pass and a human approval decision records `certification.state: approved`.

## Required evidence

1. `flutter analyze` passes.
2. `flutter test` passes.
3. ARM64 Android APK builds successfully.
4. APK artifact is uploaded by GitHub Actions.
5. Mobile/GIS end-to-end validation passes on the reference application.
6. Human approval is recorded.

## Reference pipeline

- Repository: `lundus88/fieldgis-reference`
- Workflow: `.github/workflows/android-device-cert.yml`
- Builder manifest: `vl/certification/mobile-flutter-v1.yaml`

## Activation outcome

After certification is approved, the builder may transition from `experimental` to `active` and become the official VL Android Mobile Builder. If activation validation fails, roll back to `experimental`.
