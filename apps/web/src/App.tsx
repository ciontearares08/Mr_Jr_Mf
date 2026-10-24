import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { getReadings } from "./services/api.ts";

//Define the TypeScript interface for what your APSIM/sensor data looks like
interface Reading {
  id: number | string;
  temperature: number;
  humidity: number;
  soil_moisture: number;
  timestamp: string;
}

//Your new data-fetching logic, converted into a Route Component
const Dashboard = () => {
  // Add TypeScript generics (<Reading[]>, <boolean>, <string | null>) to your state
  const [readings, setReadings] = useState<Reading[]>([]);
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
    return <p>Loading agricultural data...</p>;
  }

  if (error) {
    return <p style={{ color: "red" }}>Error: {error}</p>;
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {readings.map((reading) => (
        <div
          key={reading.id}
          style={{
            background: "#f5f5f5",
            padding: "1rem",
            borderRadius: "8px",
          }}
        >
          <p>
            <strong>Timestamp:</strong> {reading.timestamp}
          </p>
          <p>
            <strong>Temperature:</strong> {reading.temperature} °C
          </p>
          <p>
            <strong>Humidity:</strong> {reading.humidity} %
          </p>
          <p>
            <strong>Soil Moisture:</strong> {reading.soil_moisture} %
          </p>
        </div>
      ))}
    </div>
  );
};

// 3. The Main App component wrapping your Dashboard in React Router
export default function App() {
  return (
    <BrowserRouter>
      <div style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
        <header style={{ marginBottom: "2rem" }}>
          <h1>Smart Agriculture System</h1>
        </header>

        <Routes>
          {/* This sets up the routing foundation for future AWS Cognito login/settings pages */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
