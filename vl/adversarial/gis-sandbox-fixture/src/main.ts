import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

(globalThis as any).__VL_MAPLIBRE_RUNTIME__ = {
  version: maplibregl.version ?? 'unknown',
  booted: true
};
