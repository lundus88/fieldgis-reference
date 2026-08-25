import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:fieldgis_reference/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('FieldGIS Mobile/GIS capture flow', (tester) async {
    app.main();
    await tester.pumpAndSettle(const Duration(seconds: 5));

    expect(find.text('FieldGIS Reference'), findsOneWidget);
    expect(find.text('Locate'), findsOneWidget);
    expect(find.text('Capture Point'), findsOneWidget);

    final codeField = find.byType(EditableText);
    expect(codeField, findsOneWidget);
    await tester.enterText(codeField, 'E2E001');

    await tester.tap(find.text('Locate'));
    await tester.pumpAndSettle(const Duration(seconds: 8));
    expect(find.text('GPS position ready.'), findsOneWidget);

    await tester.tap(find.text('Capture Point'));
    await tester.pumpAndSettle(const Duration(seconds: 5));
    expect(find.text('E2E001 captured offline.'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.list_alt));
    await tester.pumpAndSettle();
    expect(find.text('E2E001'), findsOneWidget);
  });
}
