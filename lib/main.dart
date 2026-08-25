import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const FieldGisApp());

class FieldPoint {
  const FieldPoint({required this.id, required this.code, required this.latitude, required this.longitude, required this.accuracyM, required this.createdAt});
  final String id;
  final String code;
  final double latitude;
  final double longitude;
  final double accuracyM;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
    'id': id,
    'code': code,
    'latitude': latitude,
    'longitude': longitude,
    'accuracy_m': accuracyM,
    'sync_state': 'queued',
    'created_at': createdAt.toIso8601String(),
  };

  factory FieldPoint.fromJson(Map<String, dynamic> json) => FieldPoint(
    id: json['id'] as String,
    code: json['code'] as String,
    latitude: (json['latitude'] as num).toDouble(),
    longitude: (json['longitude'] as num).toDouble(),
    accuracyM: (json['accuracy_m'] as num).toDouble(),
    createdAt: DateTime.parse(json['created_at'] as String),
  );
}

class FieldGisApp extends StatelessWidget {
  const FieldGisApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'FieldGIS Reference',
    theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F172A)), useMaterial3: true),
    home: const FieldMapPage(),
  );
}

class FieldMapPage extends StatefulWidget {
  const FieldMapPage({super.key});
  @override
  State<FieldMapPage> createState() => _FieldMapPageState();
}

class _FieldMapPageState extends State<FieldMapPage> {
  static const _storageKey = 'fieldgis_points_v1';
  MapLibreMapController? _mapController;
  Position? _position;
  final _codeController = TextEditingController(text: 'P001');
  List<FieldPoint> _points = const [];
  String _message = 'Tap Locate to read device GPS.';
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _loadPoints();
  }

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _loadPoints() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_storageKey) ?? const [];
    final points = raw.map((e) => FieldPoint.fromJson(jsonDecode(e) as Map<String, dynamic>)).toList();
    if (mounted) setState(() => _points = points);
  }

  Future<void> _savePoints() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_storageKey, _points.map((e) => jsonEncode(e.toJson())).toList());
  }

  Future<bool> _ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      if (mounted) setState(() => _message = 'Location service is disabled.');
      return false;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      if (mounted) setState(() => _message = 'Location permission denied.');
      return false;
    }
    return true;
  }

  Future<void> _locate() async {
    if (_busy) return;
    setState(() { _busy = true; _message = 'Reading GPS…'; });
    try {
      if (!await _ensurePermission()) return;
      final position = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 20)));
      _position = position;
      await _mapController?.animateCamera(CameraUpdate.newLatLngZoom(LatLng(position.latitude, position.longitude), 17));
      if (mounted) setState(() => _message = 'GPS position ready.');
    } catch (e) {
      if (mounted) setState(() => _message = 'GPS error: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _capture() async {
    if (_position == null) {
      await _locate();
      if (_position == null) return;
    }
    final code = _codeController.text.trim().isEmpty ? 'P${(_points.length + 1).toString().padLeft(3, '0')}' : _codeController.text.trim();
    final point = FieldPoint(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      code: code,
      latitude: _position!.latitude,
      longitude: _position!.longitude,
      accuracyM: _position!.accuracy,
      createdAt: DateTime.now().toUtc(),
    );
    setState(() {
      _points = [..._points, point];
      _codeController.text = 'P${(_points.length + 1).toString().padLeft(3, '0')}';
      _message = '$code captured offline.';
    });
    await _savePoints();
    await _drawPoints();
  }

  Future<void> _drawPoints() async {
    final c = _mapController;
    if (c == null) return;
    await c.clearCircles();
    if (_points.isEmpty) return;
    await c.addCircles(_points.map((p) => CircleOptions(geometry: LatLng(p.latitude, p.longitude), circleRadius: 7, circleColor: '#0EA5E9', circleStrokeColor: '#FFFFFF', circleStrokeWidth: 2)).toList());
  }

  String _csv() => <String>[
    'code,latitude,longitude,accuracy_m,created_at',
    ..._points.map((p) => '${p.code},${p.latitude},${p.longitude},${p.accuracyM},${p.createdAt.toIso8601String()}'),
  ].join('\n');

  String _kml() {
    final marks = _points.map((p) => '<Placemark><name>${p.code}</name><Point><coordinates>${p.longitude},${p.latitude},0</coordinates></Point></Placemark>').join();
    return '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>$marks</Document></kml>';
  }

  Future<void> _export(String kind) async {
    final dir = await getTemporaryDirectory();
    final csv = kind == 'csv';
    final file = File('${dir.path}/fieldgis-points.${csv ? 'csv' : 'kml'}');
    await file.writeAsString(csv ? _csv() : _kml());
    await SharePlus.instance.share(ShareParams(title: 'FieldGIS ${csv ? 'CSV' : 'KML'} export', files: [XFile(file.path)]));
  }

  void _showPoints() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * .55,
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: _points.length,
            separatorBuilder: (_, _) => const Divider(),
            itemBuilder: (_, i) {
              final p = _points[i];
              return ListTile(title: Text(p.code), subtitle: Text('${p.latitude.toStringAsFixed(6)}, ${p.longitude.toStringAsFixed(6)} · ±${p.accuracyM.round()} m'));
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pos = _position;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
        title: const Text('FieldGIS Reference'),
        actions: [
          IconButton(onPressed: _showPoints, icon: const Icon(Icons.list_alt)),
          PopupMenuButton<String>(onSelected: _export, itemBuilder: (_) => const [
            PopupMenuItem(value: 'csv', child: Text('Export CSV')),
            PopupMenuItem(value: 'kml', child: Text('Export KML')),
          ]),
        ],
      ),
      body: Stack(children: [
        MapLibreMap(
          styleString: 'https://demotiles.maplibre.org/style.json',
          initialCameraPosition: const CameraPosition(target: LatLng(5.9804, 116.0735), zoom: 10),
          myLocationEnabled: true,
          onMapCreated: (controller) => _mapController = controller,
          onStyleLoadedCallback: _drawPoints,
        ),
        Positioned(
          left: 12, right: 12, top: 12,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(children: [
                TextField(controller: _codeController, decoration: const InputDecoration(labelText: 'Point code', border: OutlineInputBorder(), isDense: true)),
                const SizedBox(height: 10),
                Row(children: [
                  Expanded(child: _Metric('Latitude', pos?.latitude.toStringAsFixed(6) ?? '—')),
                  const SizedBox(width: 8),
                  Expanded(child: _Metric('Longitude', pos?.longitude.toStringAsFixed(6) ?? '—')),
                  const SizedBox(width: 8),
                  Expanded(child: _Metric('Accuracy', pos == null ? '—' : '±${pos.accuracy.round()} m')),
                ]),
                const SizedBox(height: 8),
                Align(alignment: Alignment.centerLeft, child: Text(_message)),
              ]),
            ),
          ),
        ),
        Positioned(
          right: 14, bottom: 20,
          child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            FloatingActionButton.extended(heroTag: 'locate', onPressed: _busy ? null : _locate, icon: const Icon(Icons.my_location), label: const Text('Locate')),
            const SizedBox(height: 10),
            FloatingActionButton.extended(heroTag: 'capture', backgroundColor: const Color(0xFF067647), foregroundColor: Colors.white, onPressed: _busy ? null : _capture, icon: const Icon(Icons.add_location_alt), label: const Text('Capture Point')),
          ]),
        ),
      ]),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value);
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(8),
    decoration: BoxDecoration(border: Border.all(color: Colors.black12), borderRadius: BorderRadius.circular(10), color: Colors.white),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
      Text(label, style: Theme.of(context).textTheme.labelSmall),
    ]),
  );
}
