import 'dart:convert';
import 'dart:io';

Future<void> main() async {
  final url = Platform.environment['VL_SUPABASE_URL'];
  final key = Platform.environment['VL_SUPABASE_PUBLISHABLE_KEY'];

  if (url == null || url.isEmpty || key == null || key.isEmpty) {
    stderr.writeln('Missing VL_SUPABASE_URL or VL_SUPABASE_PUBLISHABLE_KEY.');
    exitCode = 2;
    return;
  }

  final uri = Uri.parse('$url/rest/v1/vl_cert_health?id=eq.1&select=id,status');
  final client = HttpClient();
  try {
    final request = await client.getUrl(uri);
    request.headers.set('apikey', key);
    request.headers.set('Accept', 'application/json');

    final response = await request.close();
    final body = await utf8.decodeStream(response);
    if (response.statusCode != HttpStatus.ok) {
      stderr.writeln('Supabase Data API returned HTTP ${response.statusCode}: $body');
      exitCode = 3;
      return;
    }

    final decoded = jsonDecode(body);
    if (decoded is! List || decoded.length != 1) {
      stderr.writeln('Unexpected health payload: $body');
      exitCode = 4;
      return;
    }

    final row = decoded.first;
    if (row is! Map || row['id'] != 1 || row['status'] != 'ok') {
      stderr.writeln('Health row did not match expected contract: $body');
      exitCode = 5;
      return;
    }

    stdout.writeln('Supabase Data API integration passed: health row status=ok.');
  } finally {
    client.close(force: true);
  }
}
