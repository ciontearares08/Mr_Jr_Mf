import type { Polygon as GeoJSONPolygon } from "geojson";

/* one corner as the user typed it. Kept as text so half-typed numbers like "57." work.
The id stays the same when other rows are added or removed, so React keeps focus on the right row. */
export type CornerRow = { id: string; lat: string; lon: string };

export const MIN_CORNERS = 3;

let nextRowId = 0;

/* a new corner row with its own id */
export function newCornerRow(lat = "", lon = ""): CornerRow {
  nextRowId += 1;
  return { id: `corner-${nextRowId}`, lat, lon };
}

/* round GeoJSON to 6 decimals (about 0.1 m) */
function roundTo6(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

/* a decimal number with an optional minus sign, e.g. "57", "57." or "-8.25".
Number() alone would also accept "0x38" or "5.6e1". */
const DECIMAL_PATTERN = /^-?\d+(\.\d*)?$/;

/* typed text to number, accepts comma as decimal separator
Returns null if it is not a number. */
export function parseCoordinate(text: string): number | null {
  const cleaned = text.trim().replace(",", ".");
  if (!DECIMAL_PATTERN.test(cleaned)) {
    return null;
  }
  return Number(cleaned);
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

/* turns a polygon into rows for the inputs, returns empty rows when there's no polygon.
Rounded to 6 decimals like rowsToPolygon, so the rows show the same corners that are saved. */
export function polygonToRows(geometry: GeoJSONPolygon | null): CornerRow[] {
  if (geometry === null) {
    return Array.from({ length: MIN_CORNERS }, () => newCornerRow());
  }
  // leave out the closing corner, user only sees each corner once.
  return geometry.coordinates[0]
    .slice(0, -1)
    .map(([lon, lat]) =>
      newCornerRow(String(roundTo6(lat)), String(roundTo6(lon))),
    );
}
