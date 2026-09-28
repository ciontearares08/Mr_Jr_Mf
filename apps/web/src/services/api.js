const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

//return all readings such as (is, timestamp, temperature, humidity, soil_moisture)
export async function getReadings() {
    const response = await fetch(`${API_URL}/api/readings`);

    if (!response.ok) {
        throw new Error(`Failed to fetch readings: ${response.status}`);
    }

    return await response.json();
}

//will at some point return latest readings
export async function getLatestReading() {
    const response = await fetch(`${API_URL}/api/readings/latest`);

    if (!response.ok) {
        throw new Error("Failed to fetch latest reading");
    }

    return response.json();
}

//will at some point return readings of a specidic id
export async function getReading(id) {
    const response = await fetch(`${API_URL}/api/readings/${id}`);

    if (!response.ok) {
        throw new Error("Failed to fetch reading");
    }

    return response.json();
}