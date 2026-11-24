import type { Polygon as GeoJSONPolygon } from "geojson";
import area from "@turf/area";
import {
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FieldMapEditor } from "@/components/map/FieldMap";
import CoordinateInput from "../../CoordinateInput";

type BoundaryStepProps = {
  geometry: GeoJSONPolygon | null;
  isValid: boolean;
  outsideDenmark: boolean;
  onChange: (geometry: GeoJSONPolygon | null) => void;
};

export default function BoundaryStep({
  geometry,
  isValid,
  outsideDenmark,
  onChange,
}: BoundaryStepProps) {
  const areaHa = geometry && isValid ? area(geometry) / 10000 : null;

  return (
    <>
      <CardHeader>
        <CardTitle>Step 2: Boundary</CardTitle>
        <CardDescription>
          Draw the outline of your field on the map. You can edit or move it
          afterwards.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Tabs defaultValue="map">
          <TabsList>
            <TabsTrigger value="map">Draw field on map</TabsTrigger>
            <TabsTrigger value="coordinates">Type coordinates</TabsTrigger>
          </TabsList>
          <TabsContent value="map">
            <FieldMapEditor initialValue={geometry} onChange={onChange} />
          </TabsContent>
          <TabsContent value="coordinates">
            <CoordinateInput initialValue={geometry} onChange={onChange} />
          </TabsContent>
        </Tabs>
        <p className="text-sm" aria-live="polite">
          {geometry === null && (
            <span className="text-muted-foreground">
              Use the polygon tool in the top-left corner of the map to draw
              your field or enter at least 3 coordinates.
            </span>
          )}
          {geometry !== null && !isValid && (
            <span className="text-destructive">
              The outline is invalid. There needs to exist atleast 3 coordinates
              and the edges must not cross each other.
            </span>
          )}
          {outsideDenmark && (
            <span className="text-destructive">
              This field is outside Denmark. Weather data from DMI covers only
              Denmark, so draw the field inside Denmark.
            </span>
          )}
          {areaHa !== null && !outsideDenmark && (
            <span className="text-muted-foreground">
              Estimated area:{" "}
              <span className="font-medium text-foreground">
                {areaHa.toFixed(2)} ha
              </span>
              . The exact area is calculated when the field is saved.
            </span>
          )}
        </p>
      </CardContent>
    </>
  );
}
