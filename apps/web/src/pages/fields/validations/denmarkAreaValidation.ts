import type { Polygon as GeoJSONPolygon } from "geojson";
import booleanWithin from "@turf/boolean-within";

/* Copied the DK boundary with and without Bronholm from backend.
Help make the check also on the front end, copying and having a duplicate is easier as
it is a small file and also the check is only on the frontend this way. */
const DENMARK_WITHOUT_BORNHOLM: GeoJSONPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [7.9, 55.1],
      [8.55, 55.06],
      [8.65, 54.91],
      [8.92, 54.9],
      [9.12, 54.87],
      [9.25, 54.84],
      [9.32, 54.8],
      [9.38, 54.8],
      [9.42, 54.82],
      [9.5, 54.835],
      [9.58, 54.873],
      [9.7, 54.845],
      [9.95, 54.8],
      [10.1, 54.72],
      [11.0, 54.58],
      [12.1, 54.48],
      [12.65, 54.75],
      [12.62, 55.33],
      [12.85, 55.62],
      [12.62, 55.9],
      [12.66, 56.04],
      [12.35, 56.22],
      [12.0, 56.45],
      [11.95, 56.85],
      [11.6, 57.3],
      [11.15, 57.8],
      [10.2, 58.0],
      [7.9, 57.4],
      [7.9, 55.1], // GeoJSON repeats the first corner to close the outline
    ],
  ],
};

const BORNHOLM: GeoJSONPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [14.6, 54.95],
      [15.25, 54.95],
      [15.25, 55.35],
      [14.6, 55.35],
      [14.6, 54.95],
    ],
  ],
};

// returns True when the whole field is inside the area DMI has weather data for.
export function isInsideDenmark(geometry: GeoJSONPolygon): boolean {
  return (
    booleanWithin(geometry, DENMARK_WITHOUT_BORNHOLM) ||
    booleanWithin(geometry, BORNHOLM)
  );
}
