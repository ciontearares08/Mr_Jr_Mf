
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Help() {
  return (
    <div className="container mx-auto py-8 px-4 max-w-5xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-primary">Agricultural Terms Help</h1>
        <p className="text-muted-foreground mt-2">
          Plain-language explanations of the crop terms, soil water limits, and satellite indices used across the app.
        </p>
      </div>

      {/* Crop Terms */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Crop Terms</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">Term</TableHead>
                <TableHead>What it is</TableHead>
                <TableHead>Why it matters</TableHead>
                <TableHead className="w-[160px]">Good range</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">LAI (Leaf Area Index)</TableCell>
                <TableCell>Square metres of green leaf per square metre of ground.</TableCell>
                <TableCell>Leaves act as solar panels. Too little wastes sunlight; too much risks lodging.</TableCell>
                <TableCell>4 to 6 at flowering</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Growth stages</TableCell>
                <TableCell>The steps from sowing to harvest tracked via Zadoks (00 to 99) scale.</TableCell>
                <TableCell>Timing tells the farmer when to act; stress during flowering hurts yield most.</TableCell>
                <TableCell>Stage dates predicted</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Yield</TableCell>
                <TableCell>Weight of grain harvested per hectare (t/ha).</TableCell>
                <TableCell>The end result of crop growth and management.</TableCell>
                <TableCell>6 to 10 t/ha</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Grain protein</TableCell>
                <TableCell>Share of grain that is protein (%).</TableCell>
                <TableCell>Sets baking quality and price value.</TableCell>
                <TableCell>12 to 14%</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Grain size</TableCell>
                <TableCell>Average weight of one grain in milligrams (TGW).</TableCell>
                <TableCell>Small grains point to drought, heat, or lost leaves.</TableCell>
                <TableCell>42 to 55 mg</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Grain number</TableCell>
                <TableCell>Grains per square metre (ears × grains per ear).</TableCell>
                <TableCell>The biggest driver of final yield, fixed around flowering.</TableCell>
                <TableCell>15,000 to 30,000 / m²</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Grain total weight</TableCell>
                <TableCell>Dry weight of all grains in grams per square metre.</TableCell>
                <TableCell>The model's internal yield expression.</TableCell>
                <TableCell>500 to 850 g/m²</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">Grain total nitrogen</TableCell>
                <TableCell>Nitrogen stored in the grain (kg N/ha).</TableCell>
                <TableCell>Links overall yield and protein concentration.</TableCell>
                <TableCell>110 to 190 kg N/ha</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Soil Water Limits */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Soil Water Terms & Limits</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[220px]">Term</TableHead>
                <TableHead>What it is</TableHead>
                <TableHead>Why it matters</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">CLL (Crop Lower Limit / Wilting Point)</TableCell>
                <TableCell>The driest the soil can get while roots can still take water from it.</TableCell>
                <TableCell>Below this point, the crop enters drought stress and wilts.</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">LL15 (Lower Limit 15 bar)</TableCell>
                <TableCell>The soil water content at 15 bar suction pressure, representing the permanent wilting point.</TableCell>
                <TableCell>Defines the lower bound of available water capacity in crop and hydrological models.</TableCell>
                </TableRow>
              <TableRow>
                <TableCell className="font-medium">DUL (Drained Upper Limit / Field Capacity)</TableCell>
                <TableCell>Water retained after heavy rain has drained away (2–3 days).</TableCell>
                <TableCell>Represents the healthy "full" water level for soil.</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">SAT (Saturation)</TableCell>
                <TableCell>Every soil pore is completely filled with water.</TableCell>
                <TableCell>Prolonged days near SAT cause waterlogging and root oxygen starvation.</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">PAWC (Plant Available Water Capacity)</TableCell>
                <TableCell>Total storable water available for the crop ((DUL - CLL) × depth).</TableCell>
                <TableCell>Indicates how long the crop can survive without rain.</TableCell>
              </TableRow>
              <TableRow>
              <TableCell className="font-medium">PAW (Plant Available Water)</TableCell>
              <TableCell>The amount of water currently stored in the root zone above the lower limit.</TableCell>
              <TableCell>Measures real-time water availability to assess immediate drought stress.</TableCell>
            </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Satellite Indices */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Satellite Indices (Sentinel-2)</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[180px]">Index</TableHead>
                <TableHead>What it shows</TableHead>
                <TableHead>Why it matters</TableHead>
                <TableHead className="w-[160px]">Ranges</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="font-medium">NDVI</TableCell>
                <TableCell>Basic plant health and green biomass check.</TableCell>
                <TableCell>Follows leaf growth early in the season before canopy closure.</TableCell>
                <TableCell>0.6 to 0.9 healthy</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">NDRE</TableCell>
                <TableCell>Chlorophyll content inside the leaves.</TableCell>
                <TableCell>Remains sensitive even when NDVI saturates in dense crops.</TableCell>
                <TableCell>0.3 to 0.6 healthy</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">RECI</TableCell>
                <TableCell>Chlorophyll amount scaled linearly without upper bounds.</TableCell>
                <TableCell>Differentiates dense, well-fed crops effectively.</TableCell>
                <TableCell>Higher is more chlorophyll</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">NDWI (Gao)</TableCell>
                <TableCell>Water content inside the leaves.</TableCell>
                <TableCell>Acts as an independent satellite check against soil water stress.</TableCell>
                <TableCell>0.2 to 0.5 healthy</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="font-medium">NDWI (McFeeters)</TableCell>
                <TableCell>Open surface water and flooding detection.</TableCell>
                <TableCell>Provides an external validation check for waterlogging alerts.</TableCell>
                <TableCell>Above 0.2 water surface</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
