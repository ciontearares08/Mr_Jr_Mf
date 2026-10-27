import { useState, useEffect } from "react";
import { Calendar, CircleAlert, Droplet, Info, Sprout } from "lucide-react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { getReadings, type Reading } from "../services/mock_api";
import MetricCard from "./MetricCard";
import ReadingsTable from "./ReadingsTable";

export default function Dashboard() {
  const [readings, setReadings] = useState<Reading[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getReadings();
        setReadings(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-50 items-center justify-center">
        <Spinner className="size-8 text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Error: {error}</AlertTitle>
      </Alert>
    );
  }

  // Calculate some simple mock statistics for the cards based on the CSV data
  const maxLai = readings.length
    ? Math.max(...readings.map((r) => r.wheat_lai || 0))
    : 0;
  const avgMoisture = readings.length
    ? readings.reduce((sum, r) => sum + (r["soil_soilwater_paw(1)"] || 0), 0) /
      readings.length
    : 0;

  // The CSV has one row per day, so the first and last rows give the date range
  const firstDay = readings[0]?.clock_today.split(" ")[0];
  const lastDay = readings[readings.length - 1]?.clock_today.split(" ")[0];

  return (
    <div>
      <h2 className="mb-6 text-3xl font-bold text-primary">
        Simulation Dashboard
      </h2>

      {readings.length === 0 ? (
        <Alert>
          <Info />
          <AlertTitle>No records found. Ensure mock data is loaded.</AlertTitle>
        </Alert>
      ) : (
        <>
          {/* Top Row: Metric Cards (stacked on phones, 3 across from `sm` up) */}
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            <MetricCard
              title="Total Days Simulated"
              value={readings.length}
              description={`${firstDay} to ${lastDay}`}
              icon={<Calendar className="size-5" />}
            />
            <MetricCard
              title="Peak Leaf Area Index"
              value={maxLai.toFixed(2)}
              description="Highest leaf cover reached"
              icon={<Sprout className="size-5" />}
            />
            <MetricCard
              title="Avg Topsoil Moisture"
              value={avgMoisture.toFixed(3)}
              unit="PAW"
              description="Plant-available water, top layer"
              icon={<Droplet className="size-5" />}
            />
          </div>

          <section className="mt-8">
            <ReadingsTable data={readings} />
          </section>
        </>
      )}
    </div>
  );
}
