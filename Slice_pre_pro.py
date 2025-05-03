#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 20:40:36 2025

@author: cln3
"""

#####################################################################################
""" Imports """
#####################################################################################
import sys
import subprocess
import os
import configparser
import time
from datetime import datetime

# Add the project directory to the system path
sys.path.insert(0, '/home/cln3/SAR/')

#####################################################################################
# Load Paths from Config File
#####################################################################################
config_file_path = "/home/cln3/SAR/config.txt"
parser = configparser.ConfigParser()
parser.read(config_file_path)

# Root directory for input/output
root = parser.get("SoilMoistureMapping_config", "root")
print(f"Root directory: {root}")

# Paths for SNAP processing
graph_path = parser.get("SoilMoistureMapping_config", "graph_path_6")
SNAP_version_1 = parser.get("SoilMoistureMapping_config", "SNAP_version_1")
shapefile_path = parser.get("SoilMoistureMapping_config", "shapefile_path")

#####################################################################################
# Processing Function
#####################################################################################
def process_slice_assembly_outputs():
    input_folder = os.path.join(root, "Sentinel1/1_Slice_Assembly")
    output_folder = os.path.join(root, "Sentinel1/1_Processed_Image")
    os.makedirs(output_folder, exist_ok=True)

    # Get input files
    input_files = sorted([f for f in os.listdir(input_folder) if f.endswith(('.dim', '.zip'))])
    total_files = len(input_files)
    
    if not input_files:
        print("No input files found!")
        return

    print(f"\nStarting processing of {total_files} files...")
    print("="*60)

    for i, input_file in enumerate(input_files, 1):
        input_path = os.path.join(input_folder, input_file)
        output_filename = f"{os.path.splitext(input_file)[0]}_TC.dim"
        output_path = os.path.join(output_folder, output_filename)

        # Skip if output exists
        if os.path.exists(output_path):
            print(f"\nFile {i}/{total_files} - Skipped (exists): {output_filename}")
            continue

        print(f"\nFile {i}/{total_files} - Processing: {input_file}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_time = time.time()

        try:
            # Run SNAP processing
            subprocess.call([
                SNAP_version_1,
                graph_path,
                f'-Pinput1={input_path}',
                f'-Poutput1={output_path}',
                '-c', '2048M',
                '-q', '4'
            ])
            
            elapsed_time = (time.time() - start_time) / 60
            print(f"Completed in {elapsed_time:.2f} minutes")
            print(f"Output saved to: {output_path}")

        except Exception as e:
            elapsed_time = (time.time() - start_time) / 60
            print(f"ERROR processing {input_file} after {elapsed_time:.2f} minutes")
            print(f"Error details: {str(e)}")
            continue

    print("\n" + "="*60)
    print(f"Processing completed. {total_files} files processed.")
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    process_slice_assembly_outputs()