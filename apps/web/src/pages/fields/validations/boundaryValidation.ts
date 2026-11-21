import type { Polygon as GeoJSONPolygon } from "geojson";
import area from "@turf/area";
import kinks from "@turf/kinks";

/**
 * Checks the boundary before the user can leave step 2. Mirrors the API's
 * rules, except "inside Denmark", which the server checks on submit.
 */
export function isBoundaryValid(geometry: GeoJSONPolygon | null): boolean {
  if (geometry === null || geometry.coordinates.length !== 1) {
    return false;
  }
  const ring = geometry.coordinates[0];
  // At least 3 corners plus the closing point, and the ring must be closed.
  if (ring.length < 4) {
    return false;
  }
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) {
    return false;
  }
  const inRange = ring.every(
    ([lon, lat]) =>
      Number.isFinite(lon) &&
      Number.isFinite(lat) &&
      lon >= -180 &&
      lon <= 180 &&
      lat >= -90 &&
      lat <= 90,
  );
  if (!inRange) {
    return false;
  }
  // Every corner must be different (the closing point is left out).
  const corners = ring.slice(0, -1);
  const unique = new Set(corners.map(([lon, lat]) => `${lon},${lat}`));
  if (unique.size !== corners.length) {
    return false;
  }
  // kinks() returns the points where the outline crosses itself.
  const crossesItself = kinks(geometry).features.length > 0;
  return !crossesItself && area(geometry) > 0;
}
