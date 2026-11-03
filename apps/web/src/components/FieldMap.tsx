import { useEffect, useRef, useState } from "react";
import * as Leaflet from "leaflet";
import type { Polygon as GeoJSONPolygon } from "geojson";
import "@geoman-io/leaflet-geoman-free";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import area from "@turf/area";

const position = [56.2639, 10.5];
const zoom = 7;

export default function FieldMap() {
  const container = useRef<HTMLDivElement>(null);
  //   const features = useRef<Leaflet.FeatureGroup | null>(null);
  const [polygon, setPolygon] = useState<GeoJSONPolygon | null>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = Leaflet.map(container.current).setView(
      [position[0], position[1]],
      zoom,
    );
    // this is a token free example base map. Can choose a different one later for our prod app
    Leaflet.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const drawn = Leaflet.featureGroup().addTo(map);
    // features.current = drawn;
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
    });

    const refresh = () => {
      const layer = drawn.getLayers()[0];
      if (layer instanceof Leaflet.Polygon) {
        const geometry = layer.toGeoJSON().geometry;
        setPolygon(geometry.type === "Polygon" ? geometry : null);
      } else {
        setPolygon(null);
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
      map.remove();
      //   features.current = null;
    };
  }, []);

  const areaHa = polygon ? area(polygon) / 10000 : null;

  return (
    <section>
      <div ref={container} style={{ height: "60vh", minHeight: 320 }} />
      <p>
        {areaHa === null
          ? "Draw a Polygon to add your field."
          : `Estimated Area: ${areaHa.toFixed(2)} ha`}
      </p>
      <pre aria-label="Exported GeoJSON">
        {polygon ? JSON.stringify(polygon, null, 2) : ""}
      </pre>
    </section>
  );
}
