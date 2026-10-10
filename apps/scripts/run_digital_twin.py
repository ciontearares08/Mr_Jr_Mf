import os
import shutil
import glob
import sqlite3
import pandas as pd
from apsimNGpy.core import ApsimModel

def run_digital_twin_simulation(apsimx_file, data_dir, script_dir):
    if not os.path.exists(apsimx_file):
        print(f"Error: Could not find {apsimx_file}")
        return None

    print(f"Initializing APSIM Next Generation model: {apsimx_file}...")
    
    cwd_scratch = os.path.join(os.getcwd(), ".scratch")
    os.makedirs(cwd_scratch, exist_ok=True)
    
    # Check for the weather file in the data folder first, then script folder
    weather_filename = "Copenhagen_Weather.met"
    weather_src_data = os.path.join(data_dir, weather_filename)
    weather_src_script = os.path.join(script_dir, weather_filename)
    
    # Destination is the .scratch folder created by apsimNGpy
    weather_dest = os.path.join(cwd_scratch, weather_filename)
    
    try:
        if os.path.exists(weather_src_data):
            shutil.copy(weather_src_data, weather_dest)
        elif os.path.exists(weather_src_script):
            shutil.copy(weather_src_script, weather_dest)
        else:
            print(f"Error: {weather_filename} not found in {data_dir} or {script_dir}.")
            return None
    except Exception as e:
        print(f"Error copying weather file: {e}")
        return None
    
    # Initialize and run model
    model = ApsimModel(apsimx_file)
    print("Running simulation...")
    model.run()
    
    # Locate generated SQLite database inside the terminal's .scratch folder
    db_files = glob.glob(os.path.join(cwd_scratch, "*.db"))
    
    if not db_files:
        print("Error: No SQLite database files found after running simulation.")
        return None
        
    latest_db_temp = max(db_files, key=os.path.getmtime)
    
    
    db_filename = os.path.basename(latest_db_temp)
    db_path = os.path.join(data_dir, db_filename)
    shutil.copy(latest_db_temp, db_path)
    print(f"Simulation database saved to: {db_path}")

    # Read tables from database (now reading from the saved copy in data/)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    # Filter out system tables to find the report table
    data_tables = [t for t in tables if not t.startswith('_') and t not in ['sqlite_sequence', 'Checkpoints', 'Simulations', 'Units']]
    
    if not data_tables:
        print("\n[ERROR]: No valid simulation report tables found.")
        conn.close()
        return None
        
    target_table = data_tables[0]
    print(f"Reading data from table: {target_table}")
    
    # Load entire simulation into a Pandas DataFrame
    df = pd.read_sql_query(f"SELECT * FROM [{target_table}]", conn)
    conn.close()
    
    if df is not None and not df.empty:
        # Export the full day-by-day timeline to the data folder
        output_csv = os.path.join(data_dir, "copenhagen_wheat_daily_telemetry.csv")
        df.to_csv(output_csv, index=False)
        print(f"Successfully exported full daily time-series to: {output_csv}")

        # Find peak growth metrics for validation
        lai_col = next((col for col in df.columns if 'LAI' in col), None)
        
        if lai_col:
            active_growth = df[df[lai_col] > 0]
            if not active_growth.empty:
                peak_crop_day = active_growth.loc[active_growth[lai_col].idxmax()]
            else:
                peak_crop_day = df.iloc[-1]
                print("Warning: Crop never sprouted (LAI remained 0 throughout the year).")
            lai = peak_crop_day.get(lai_col, 0)
        else:
            peak_crop_day = df.iloc[-1]
            lai = 0.0
            
        total_paw = sum(
            peak_crop_day.get(col, 0) 
            for col in df.columns if 'SoilWater.PAW' in col
        )
        
        date = peak_crop_day.get('Clock.Today', peak_crop_day.get('Date', 'Unknown'))
        
        print("\n--- Peak Season Simulation Summary ---")
        print(f"Date of Max Growth: {date}")
        print(f"Simulated Total Soil Moisture (PAW): {total_paw:.2f} mm")
        print(f"Simulated Peak Leaf Area Index (LAI): {lai:.2f}")
        
        return df
    else:
        print("Error: Extracted DataFrame is empty.")
        return None

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    
    # Target the .apsimx file directly inside the data folder
    project_file = os.path.join(data_dir, "Project6_Model.apsimx")
    
    # Pass the directories to the function
    daily_dataframe = run_digital_twin_simulation(project_file, data_dir, script_dir)