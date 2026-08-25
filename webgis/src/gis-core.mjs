export function gpsMarker(latitude, longitude, accuracyM = null) {
  if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) throw new RangeError('Invalid latitude');
  if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) throw new RangeError('Invalid longitude');
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [longitude, latitude] },
    properties: { accuracy_m: accuracyM }
  };
}

export function featureCollection(features = []) {
  return { type: 'FeatureCollection', features };
}

function esc(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

export function pointToKml(feature, name = 'VL GPS Point') {
  if (feature?.geometry?.type !== 'Point') throw new TypeError('Point feature required');
  const [lon, lat] = feature.geometry.coordinates;
  return `<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>${esc(name)}</name><Point><coordinates>${lon},${lat},0</coordinates></Point></Placemark></Document></kml>`;
}

export async function mapLibreRuntimeContract() {
  const maplibre = await import('maplibre-gl');
  return {
    mapConstructor: typeof maplibre.Map === 'function',
    markerConstructor: typeof maplibre.Marker === 'function',
    navigationControl: typeof maplibre.NavigationControl === 'function'
  };
}
