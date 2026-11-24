import { useState } from "react";
import type { Polygon as GeoJSONPolygon } from "geojson";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type CornerRow,
  MIN_CORNERS,
  isCoordinateInvalid,
  newCornerRow,
  polygonToRows,
  rowsToPolygon,
} from "./coordinates";

type CoordinateInputProps = {
  initialValue: GeoJSONPolygon | null;
  onChange: (geometry: GeoJSONPolygon | null) => void;
};

export default function CoordinateInput({
  initialValue,
  onChange,
}: CoordinateInputProps) {
  /* Only read when the tab is opened, the tab is rebuilt each time it is shown,
    so it always starts from the latest polygon */
  const [rows, setRows] = useState<CornerRow[]>(() =>
    polygonToRows(initialValue),
  );
  // true once the wizard holds an outline, from the map or from these rows
  const [hasOutline, setHasOutline] = useState(initialValue !== null);
  const isComplete = rowsToPolygon(rows) !== null;

  /* The field only changes when every row is a number. While a row is empty or
    half typed (e.g. right after "Add corner"), the wizard keeps the last complete
    outline, so switching back to the map does not lose the field. */
  const update = (next: CornerRow[]) => {
    setRows(next);
    const polygon = rowsToPolygon(next);
    if (polygon !== null) {
      onChange(polygon);
      setHasOutline(true);
    }
  };
  const setCell = (id: string, key: "lat" | "lon", value: string) =>
    update(
      rows.map((row) => (row.id === id ? { ...row, [key]: value } : row)),
    );
  const addCorner = () => update([...rows, newCornerRow()]);
  const removeCorner = (id: string) =>
    update(rows.filter((row) => row.id !== id));

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Enter the corners in order around the edge of your field, in decimal
        degrees. In Denmark, latitude is about 54.5 to 57.8 and longitude about
        8 to 15.
      </p>
      <ol className="space-y-2">
        {rows.map((row, index) => {
          const latId = `${row.id}-lat`;
          const lonId = `${row.id}-lon`;
          // Show the labels above the first row only; the others keep them for screen readers.
          const labelClass = index > 0 ? "sr-only" : undefined;
          return (
            <li key={row.id} className="flex items-end gap-2">
              <span className="w-6 pb-1.5 text-sm text-muted-foreground">
                {index + 1}.
              </span>
              <div className="flex-1 space-y-1">
                <Label htmlFor={latId} className={labelClass}>
                  Latitude
                </Label>
                <Input
                  id={latId}
                  inputMode="decimal"
                  placeholder="e.g. 57.0481"
                  value={row.lat}
                  aria-invalid={isCoordinateInvalid(row.lat, 90)}
                  onChange={(e) => setCell(row.id, "lat", e.target.value)}
                />
              </div>
              <div className="flex-1 space-y-1">
                <Label htmlFor={lonId} className={labelClass}>
                  Longitude
                </Label>
                <Input
                  id={lonId}
                  inputMode="decimal"
                  placeholder="e.g. 9.9187"
                  value={row.lon}
                  aria-invalid={isCoordinateInvalid(row.lon, 180)}
                  onChange={(e) => setCell(row.id, "lon", e.target.value)}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove corner ${index + 1}`}
                disabled={rows.length <= MIN_CORNERS}
                onClick={() => removeCorner(row.id)}
              >
                <X />
              </Button>
            </li>
          );
        })}
      </ol>
      {!isComplete && hasOutline && (
        <p className="text-sm text-muted-foreground" aria-live="polite">
          Fill in every corner to update the field. Until then, the field keeps
          its last complete outline.
        </p>
      )}
      <Button type="button" variant="outline" size="sm" onClick={addCorner}>
        <Plus data-icon="inline-start" />
        Add corner
      </Button>
    </div>
  );
}
