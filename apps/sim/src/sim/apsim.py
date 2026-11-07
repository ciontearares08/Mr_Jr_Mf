import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
import pandas as pd

def run_season(
    model_path: str | Path,
    weather_path: str | Path,
    sowing_date: str,
    soil_type: str | None = None
) -> pd.DataFrame:
    """
    Copies the APSIM model to a temporary directory, runs one season,
    and returns the daily Report dataframe including multi-layer soil water (SW) and PAW.
    """
    model_path = Path(model_path)
    weather_path = Path(weather_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        temp_model_path = temp_dir_path / model_path.name
        
        # 1. Copy model to temp folder to prevent SQLite .db locking
        shutil.copy2(model_path, temp_model_path)

        # 2. Modify the APSIM JSON directly
        with open(temp_model_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        def traverse(node):
            if isinstance(node, dict):
                # Update weather
                if node.get("$type") == "Models.Climate.Weather, Models":
                    node["FileName"] = str(weather_path)
                # Update Sowing Date
                if node.get("Name") == "SowingRule":
                    for param in node.get("Parameters", []):
                        if param.get("Key") == "SowingDate":
                            param["Value"] = sowing_date
                
                for val in node.values():
                    traverse(val)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)
                    
        traverse(data)
        
        with open(temp_model_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # 3. Run the simulation natively
        apsim_bin = shutil.which("Models")
        if not apsim_bin:
            raise FileNotFoundError("APSIM 'Models' executable not found. Is it installed?")

        try:
            command = f'"{apsim_bin}" "{temp_model_path}"'
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"APSIM execution failed!\nSTDERR: {e.stderr}\nSTDOUT: {e.stdout}")

        # 4. Extract Report table from the output SQLite database
        db_path = temp_model_path.with_suffix('.db')
        if not db_path.exists():
            raise ValueError(f"Simulation failed. No .db file found at {db_path}")

        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM Report", conn)

        # 5. Map core columns
        rename_map = {
            'Clock.Today': 'date',
            '[Clock].Today': 'date',
            'Wheat.LAI': 'lai',
            '[Wheat].LAI': 'lai',
            'Wheat.Phenology.Zadok.Stage': 'zadoks',
            '[Wheat].Phenology.Zadok.Stage': 'zadoks',
            'Wheat.Phenology.CurrentStageName': 'stage',
            '[Wheat].Phenology.CurrentStageName': 'stage',
            'Wheat.AboveGround.Wt': 'biomass',
            '[Wheat].AboveGround.Wt': 'biomass',
            'Yield': 'yield', 
            'Soil.SoilWater.PAW': 'paw',
            '[Soil].SoilWater.PAW': 'paw'
        }

        # Auto-detect PAW and multi-layer SW columns dynamically from APSIM output
        sw_columns = []
        for col in df.columns:
            upper_col = col.upper()
            if 'PAW' in upper_col and col not in rename_map:
                rename_map[col] = 'paw'
            elif 'SW' in upper_col and col not in rename_map and 'SOWING' not in upper_col:
                match = re.search(r'SW[^\d]*(\d+)', upper_col)
                if match:
                    layer_num = match.group(1)
                    clean_name = f"sw_{layer_num}"
                    rename_map[col] = clean_name
                    if clean_name not in sw_columns:
                        sw_columns.append(clean_name)

        df = df.rename(columns=rename_map)
        
        # Define expected columns dynamically including soil water layers
        base_expected_cols = ['date', 'lai', 'zadoks', 'stage', 'biomass', 'yield', 'paw']
        expected_cols = base_expected_cols + sw_columns
        
        existing_expected_cols = [col for col in expected_cols if col in df.columns]
        
        return df[existing_expected_cols]