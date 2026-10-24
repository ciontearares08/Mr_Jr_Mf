const API_URL = "http://localhost:8000/api";

// Exporting the interface allows you to reuse this exact type in your components
export interface Reading {
  id: string | number;
  temperature: number;
  humidity: number;
  soil_moisture: number;
  timestamp: string;
}

export async function getReadings(): Promise<Reading[]> {
  try {
    // Adjust the endpoint path if your FastAPI route is named differently
    const response = await fetch(`${API_URL}/simulations`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const json = await response.json();
    
    // Returns the array of readings. 
    // If your FastAPI endpoint wraps the array in a dictionary (e.g., { "data": [...] }), 
    // this safely falls back to extracting json.data
    return Array.isArray(json) ? json : (json.data || []);
    
  } catch (error) {
    console.error("Error fetching agricultural readings:", error);
    // Re-throw the error so the Dashboard component can catch it and update the UI
    throw error; 
  }
}