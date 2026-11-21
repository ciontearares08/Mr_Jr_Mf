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
  /* Only read when the tab is opens, the tab is rebuilt each time it is shown,
    so it always starts from the latest polygon */
  const [rows, setRows] = useState<CornerRow[]>(() =>
    polygonToRows(initialValue),
  );

  const update = (next: CornerRow[]) => {
    setRows(next);
    onChange(rowsToPolygon(next));
  };
  const setCell = (index: number, key: keyof CornerRow, value: string) =>
    update(
      rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    );
  const addCorner = () => update([...rows, { lat: "", lon: "" }]);
  const removeCorner = (index: number) =>
    update(rows.filter((_, i) => i !== index));

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Enter the corners in order around the edge of your field, in decimal
        degrees. In Denmark, latitude is about 54.5 to 57.8 and longitude about
        8 to 15.
      </p>
      <ol className="space-y-2">
        {rows.map((row, index) => {
          const latId = `corner-${index}-lat`;
          const lonId = `corner-${index}-lon`;
          // Show the labels above the first row only; the others keep them for screen readers.
          const labelClass = index > 0 ? "sr-only" : undefined;
          return (
            <li key={index} className="flex items-end gap-2">
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
                  onChange={(e) => setCell(index, "lat", e.target.value)}
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
                  onChange={(e) => setCell(index, "lon", e.target.value)}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove corner ${index + 1}`}
                disabled={rows.length <= MIN_CORNERS}
                onClick={() => removeCorner(index)}
              >
                <X />
              </Button>
            </li>
          );
        })}
      </ol>
      <Button type="button" variant="outline" size="sm" onClick={addCorner}>
        <Plus data-icon="inline-start" />
        Add corner
      </Button>
    </div>
  );
}
