import { useState, useEffect } from "react";
import { Box, Typography, Grid, CircularProgress, Alert } from "@mui/material";
import GrassIcon from "@mui/icons-material/Grass";
import WaterDropIcon from "@mui/icons-material/WaterDrop";
import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import { getReadings } from "../services/mock_api";
import MetricCard from "./MetricCard";
import ReadingsTable from "./ReadingsTable";

export default function Dashboard() {
  const [readings, setReadings] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getReadings();
        setReadings(data);
      } catch (err: any) {
        setError(err.message || "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "200px",
        }}
      >
        <CircularProgress color="success" />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">Error: {error}</Alert>;
  }

  // Calculate some simple mock statistics for the cards based on the CSV data
  const maxLai = readings.length
    ? Math.max(...readings.map((r) => r.wheat_lai || 0))
    : 0;
  const avgMoisture = readings.length
    ? readings.reduce((sum, r) => sum + (r["soil_soilwater_paw(1)"] || 0), 0) /
      readings.length
    : 0;

  return (
    <Box>
      <Typography
        variant="h4"
        component="h2"
        gutterBottom
        sx={{ fontWeight: "bold", color: "#166534" }}
      >
        Simulation Dashboard
      </Typography>

      {readings.length === 0 ? (
        <Alert severity="info">
          No records found. Ensure mock data is loaded.
        </Alert>
      ) : (
        <>
          <Box>
            {/* Top Row: Metric Cards */}
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <MetricCard
                  title="Total Days Simulated"
                  value={readings.length}
                  icon={<CalendarMonthIcon fontSize="large" />}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <MetricCard
                  title="Peak Leaf Area Index"
                  value={maxLai.toFixed(2)}
                  icon={<GrassIcon fontSize="large" />}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <MetricCard
                  title="Avg Topsoil Moisture"
                  value={avgMoisture.toFixed(3)}
                  unit="PAW"
                  icon={<WaterDropIcon fontSize="large" />}
                />
              </Grid>
            </Grid>

            <Box sx={{ mt: 10 }}>
              <Typography
                variant="h6"
                gutterBottom
                sx={{ mt: 2, mb: 4, fontWeight: "bold" }}
              >
                Daily Telemetry Log
              </Typography>
              <ReadingsTable data={readings} />
            </Box>
          </Box>
        </>
      )}
    </Box>
  );
}
