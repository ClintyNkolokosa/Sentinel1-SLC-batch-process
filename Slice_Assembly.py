#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 20:24:31 2025

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
graph_path = parser.get("SoilMoistureMapping_config", "graph_path_5")  # SNAP XML graph location
SNAP_version_1 = parser.get("SoilMoistureMapping_config", "SNAP_version_1")  # SNAP version


#####################################################################################
# SNAP Graph: SAR Image Pre-processing with Slice Assembly
# This processes pairs of images in slice assembly mode
# Processing time approx 30 per image pair
#####################################################################################

# List all raw image files in the input directory
input_folder = os.path.join(root, "Sentinel1/0_GRD_Raw_Image")
input_files = sorted([f for f in os.listdir(input_folder) if f.endswith('.zip')])

# Output directory for processed images
output_folder = os.path.join(root, "Sentinel1/1_Slice_Assembly")
os.makedirs(output_folder, exist_ok=True)

# Process images in pairs for slice assembly
for i in range(0, len(input_files), 2):
    if i+1 >= len(input_files):
        print(f"Skipping {input_files[i]} as it doesn't have a pair for slice assembly")
        continue
        
    input1 = os.path.join(input_folder, input_files[i])
    input2 = os.path.join(input_folder, input_files[i+1])
    
    # Create output filename based on the first input file
    output_filename = os.path.splitext(input_files[i])[0] + ".dim"
    output_path = os.path.join(output_folder, output_filename)
    
    # Check if output already exists
    if os.path.exists(output_path):
        print(f"Output {output_filename} already exists. Skipping processing.")
        continue
    
    print(f"Processing pair: {input_files[i]} and {input_files[i+1]}")
    print(f"Output will be saved as: {output_filename}")
    
    # Build the command for SNAP
    command = [
        SNAP_version_1,
        graph_path,
        f"-Pinput1={input1}",
        f"-Pinput2={input2}",
        f"-Poutput1={output_path}"
    ]
    
    # Print the command for debugging
    print("Executing command:", " ".join(command))
    
    # Start timer
    start_time = time.time()
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run the command
        subprocess.run(command, check=True)
        print(f"Successfully processed {output_filename}")
    except subprocess.CalledProcessError as e:
        print(f"Error processing {input_files[i]} and {input_files[i+1]}: {e}")
        continue
    
    # End timer
    end_time = time.time()
    processing_time = end_time - start_time
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Processing time: {processing_time/60:.2f} minutes\n")

print("All available pairs processed.")