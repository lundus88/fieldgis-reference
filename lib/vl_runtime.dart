import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:ui';

import 'package:flutter/foundation.dart';

class VlRuntimeConfig {
  static const certificationEnv = String.fromEnvironment(
    'VL_CERT_ENV',
    defaultValue: 'unset',
  );

  static bool get certificationInjected => certificationEnv != 'unset';
}

class VlRuntimeLogger {
  static void install() {
    final previousFlutter = FlutterError.onError;
    FlutterError.onError = (details) {
      error(
        'flutter_error',
        details.exception,
        details.stack,
      );
      previousFlutter?.call(details);
    };

    PlatformDispatcher.instance.onError = (exception, stack) {
      error('platform_error', exception, stack);
      return false;
    };
  }

  static void info(String event, [Map<String, Object?> fields = const {}]) {
    _emit('info', event, fields);
  }

  static void error(String event, Object error, StackTrace? stack) {
    _emit('error', event, {
      'error': error.toString(),
      if (stack != null) 'stack': stack.toString(),
    });
  }

  static void _emit(String level, String event, Map<String, Object?> fields) {
    final payload = jsonEncode({
      'level': level,
      'event': event,
      'ts': DateTime.now().toUtc().toIso8601String(),
      ...fields,
    });
    developer.log(payload, name: 'vl.runtime');
    if (kDebugMode) {
      debugPrint(payload);
    }
  }
}
