import type { Polygon as GeoJSONPolygon } from "geojson";

/* one corner as the user typed it. Kept as text so half-typed numbers like "57." work. */
export type CornerRow = { lat: string; lon: string };

export const MIN_CORNERS = 3;

/* round GeoJSOn to 6 decimals */
function roundTo6(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

/* typed text to number, accepts comma as decimal separator
Returns null if it is not a number. */
export function parseCoordinate(text: string): number | null {
  const cleaned = text.trim().replace(",", ".");
  if (cleaned === "") {
    return null;
  }
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

/* returns True when the text is filled in but is not a valid latitude or longitude. */
export function isCoordinateInvalid(text: string, max: number): boolean {
  if (text.trim() === "") {
    return false;
  }
  const value = parseCoordinate(text);
  return value === null || value < -max || value > max;
}

/* turns the typed rows into a GeoJSON polygon, or null while a row is empty
or not a number. GeoJSON order is [lon, lat] and the first corner is
repeated at the end to close the outline. */
export function rowsToPolygon(rows: CornerRow[]): GeoJSONPolygon | null {
  if (rows.length < MIN_CORNERS) {
    return null;
  }
  const ring: number[][] = [];
  for (const row of rows) {
    const lat = parseCoordinate(row.lat);
    const lon = parseCoordinate(row.lon);
    if (lat === null || lon === null) {
      return null;
    }
    ring.push([roundTo6(lon), roundTo6(lat)]);
  }
  ring.push([...ring[0]]);
  return { type: "Polygon", coordinates: [ring] };
}

/* turns a polygon into rows for the inputs, returns empty rows when there's no polygon */
export function polygonToRows(geometry: GeoJSONPolygon | null): CornerRow[] {
  if (geometry === null) {
    return Array.from({ length: MIN_CORNERS }, () => ({ lat: "", lon: "" }));
  }
  // leave out the closing corner, user only sees each corner once.
  return geometry.coordinates[0]
    .slice(0, -1)
    .map(([lon, lat]) => ({ lat: String(lat), lon: String(lon) }));
}
