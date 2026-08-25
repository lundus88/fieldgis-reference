import 'package:flutter_test/flutter_test.dart';
import 'package:fieldgis_reference/vl_runtime.dart';

void main() {
  test('VL certification environment is injected', () {
    expect(VlRuntimeConfig.certificationEnv, 'certification');
    expect(VlRuntimeConfig.certificationInjected, isTrue);
  });

  test('VL structured logger can install and emit', () {
    expect(() => VlRuntimeLogger.install(), returnsNormally);
    expect(
      () => VlRuntimeLogger.info('certification_probe', {'source': 'flutter_test'}),
      returnsNormally,
    );
  });
}
