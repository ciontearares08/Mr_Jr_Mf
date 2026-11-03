import { useEffect, useState } from "react";
import * as Leaflet from "leaflet";
import type { Polygon as GeoJSONPolygon } from "geojson";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import "@geoman-io/leaflet-geoman-free";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import area from "@turf/area";
import { Info, Ruler } from "lucide-react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import MetricCard from "../MetricCard";

const position: Leaflet.LatLngTuple = [56.2639, 10.5];
const zoom = 7;

type DrawControlsProps = {
  onChange: (polygon: GeoJSONPolygon | null) => void;
};

function DrawControls({ onChange }: DrawControlsProps) {
  const map = useMap();

  useEffect(() => {
    const drawn = Leaflet.featureGroup().addTo(map);
    map.pm.addControls({
      position: "topleft",
      drawMarker: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      drawText: false,
      editMode: true,
      dragMode: true,
      snappingOption: true,
      cutPolygon: false,
      rotateMode: false,
    });
    const refresh = () => {
      const layer = drawn.getLayers()[0];
      if (layer instanceof Leaflet.Polygon) {
        const geometry = layer.toGeoJSON().geometry;
        onChange(geometry.type === "Polygon" ? geometry : null);
      } else {
        onChange(null);
      }
      map.pm.Toolbar.setButtonDisabled(
        // disables the draw polygon button in the toolbar when there is already an existing polygon on the map
        "drawPolygon",
        drawn.getLayers().length > 0,
      );
    };
    const onCreate: Leaflet.PM.CreateEventHandler = (event) => {
      drawn.addLayer(event.layer);
      event.layer.on("pm:edit", refresh);
      event.layer.on("pm:dragend", refresh);
      refresh();
    };
    const onRemove: Leaflet.PM.CreateEventHandler = (event) => {
      drawn.removeLayer(event.layer);
      refresh();
    };

    map.on("pm:create", onCreate);
    map.on("pm:remove", onRemove);

    return () => {
      map.off("pm:create", onCreate);
      map.off("pm:remove", onRemove);
      map.pm.removeControls();
      map.removeLayer(drawn);
    };
  }, [map, onChange]);
  return null;
}

export default function FieldMap() {
  const [polygon, setPolygon] = useState<GeoJSONPolygon | null>(null);
  const areaHa = polygon ? area(polygon) / 10000 : null;

  return (
    <div>
      <h2 className="mb-6 text-3x1 font-bold text-primary">Field Map</h2>
      <Card>
        <CardHeader>
          <CardTitle>Draw Your Field</CardTitle>
          <CardDescription>
            Use the polygon draw tool on the map to make an outline of your
            field.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <MapContainer
            center={position}
            zoom={zoom}
            className="relative z-0 h-[60vh] min-h-80 w-full overflow-hidden rounded-lg"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <DrawControls onChange={setPolygon} />
          </MapContainer>
        </CardContent>
      </Card>
      <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
        <MetricCard
          title="Estimated Area"
          value={areaHa === null ? "0" : areaHa.toFixed(2)}
          unit={areaHa === null ? undefined : "ha"}
          description="Estimated Area on the frontend"
          icon={<Ruler className="size-5" />}
        />
        <Card className="sm:col-span-2">
          <CardHeader>
            <CardTitle>Get GeoJSON</CardTitle>
            <CardDescription>
              Polygon Data to be sent to the backend
            </CardDescription>
          </CardHeader>
          <CardContent>
            {polygon ? (
              <pre
                aria-label="Exported GeoJSON"
                className="max-h-80 overflow-auto rounded-lg bg-muted p-3 text-xs"
              >
                {JSON.stringify(polygon, null, 2)}
              </pre>
            ) : (
              <Alert>
                <Info />
                <AlertTitle>Draw a Polygon to add a field.</AlertTitle>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
