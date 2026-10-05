import { Map, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';

setWorkerUrl(workerUrl);

const map = new Map({
  container: 'map',
  style: 'https://demotiles.maplibre.org/style.json',
  center: [116.0735, 5.9804],
  zoom: 10
});
map.addControl(new NavigationControl(), 'top-right');

(globalThis as any).__VL_MAPLIBRE_RUNTIME__ = {
  booted: true,
  worker_url: workerUrl
};
