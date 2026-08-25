import test from 'node:test';
import assert from 'node:assert/strict';
import { gpsMarker, pointToKml, mapLibreRuntimeContract } from '../src/gis-core.mjs';

test('gps marker creates valid GeoJSON point', () => {
  const f = gpsMarker(5.9804, 116.0735, 3.2);
  assert.equal(f.type, 'Feature');
  assert.deepEqual(f.geometry.coordinates, [116.0735, 5.9804]);
  assert.equal(f.properties.accuracy_m, 3.2);
});

test('KML export contains coordinate and escaped name', () => {
  const f = gpsMarker(5.9804, 116.0735);
  const kml = pointToKml(f, 'A&B');
  assert.match(kml, /116\.0735,5\.9804,0/);
  assert.match(kml, /A&amp;B/);
  assert.match(kml, /<kml xmlns="http:\/\/www\.opengis\.net\/kml\/2\.2">/);
});

test('MapLibre runtime exports required constructors', async () => {
  const contract = await mapLibreRuntimeContract();
  assert.deepEqual(contract, {
    mapConstructor: true,
    markerConstructor: true,
    navigationControl: true
  });
});
