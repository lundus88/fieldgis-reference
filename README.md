# FieldGIS Reference

Reference Software #2 for VRS Labs Software Factory.

## Goal

A mobile-first Android GIS/GNSS field capture application used to validate the VRS Mobile + GIS builder path.

## Current capabilities

- Device GPS location and accuracy
- MapLibre map
- Capture point with point code
- Local/offline persistence
- Captured point list
- CSV export
- KML export
- Android APK CI build via GitHub Actions

## Safety / accuracy

FieldGIS Reference is a preliminary field-assistance application. Phone GPS accuracy is not cadastral or survey-grade and must not be represented as professional GNSS survey observations.

## Local development

Requires Flutter stable with Dart 3.10+.

```bash
flutter create . --platforms=android --org com.vrslabs --project-name fieldgis_reference
flutter pub get
flutter run
```

For Android, ensure `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, and `INTERNET` permissions are present in `android/app/src/main/AndroidManifest.xml`. The CI workflow inserts them automatically before the APK build.

## Android APK

GitHub Actions workflow: `.github/workflows/android-apk.yml`

On push to `main`, CI installs Flutter and Java 17, generates the Android platform scaffold, analyzes/tests the project, builds a debug APK, and uploads it as the `fieldgis-reference-debug-apk` artifact.

## Web/PWA reference

The tested mobile-first PWA source is retained under `pwa/` for comparison with the native Flutter build.

## VRS release policy

Production release remains locked. APK CI output is a test artifact only until Mobile/GIS E2E and human approval gates pass.
