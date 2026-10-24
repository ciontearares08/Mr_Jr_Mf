import Papa from "papaparse";

export interface Reading {
  clock_today: string;
  wheat_lai: number;
  wheat_phenology_current_stage_name: string;
  wheat_above_ground_wt: number;
  "soil_soilwater_paw(1)": number;
  temperature?: number;
  humidity?: number; 
  soil_moisture?: number;
  timestamp?: string;
  id?: string | number;
}

export async function getReadings(): Promise<Reading[]> {
  try {
    // 1. Fetch the CSV file directly from the Vite public/assets folder
    const response = await fetch("/assets/zealand_cleaned.csv");
    
    if (!response.ok) {
      throw new Error(`Could not fetch mock CSV: ${response.statusText}`);
    }

    const csvText = await response.text();

    // 2. Wrap PapaParse in a Promise so we can await the asynchronous parsing
    return new Promise((resolve, reject) => {
      Papa.parse(csvText, {
        header: true,         // Uses the first row (clock_today, etc.) as object keys
        dynamicTyping: true,  // Automatically converts numbers (e.g. "0.323" -> 0.323)
        skipEmptyLines: true,
        complete: (results) => {
          // Add a generic ID to each row so React map() has a unique key
          const parsedData = results.data.map((row: any, index: number) => ({
            ...row,
            id: index
          })) as Reading[];
          
          resolve(parsedData);
        },
        error: (error: any) => {
          reject(error);
        }
      });
    });

  } catch (error) {
    console.error("Failed to load APSIM mock data:", error);
    return [];
  }
}