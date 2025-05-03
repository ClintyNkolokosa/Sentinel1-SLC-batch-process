#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sentinel-1 SLC SNAP Coregistration Script
"""

import os
import glob
import subprocess
import configparser
from datetime import datetime
import time
import shutil

# Load config
config_file = "/home/cln3/SAR/config.txt"
parser = configparser.ConfigParser()
parser.read(config_file)
root = parser.get("SoilMoistureMapping_config", "root")
graph_path = parser.get("SoilMoistureMapping_config", "graph_path_2")
snap_exec = parser.get("SoilMoistureMapping_config", "SNAP_version_2")

# Master
master = glob.glob(os.path.join(root, "SLC/2_Step", "*dim"))[0]

# 1. Coregistration
raw_files = os.listdir(os.path.join(root, "SLC/0_Raw_Image"))

for i, fname in enumerate(raw_files):
    date_str = fname.split('_')[5].split('T')[0]
    formatted = datetime.strptime(date_str, "%Y%m%d").strftime("%Y_%b_%d")
    
    input_dim = os.path.join(root, "SLC/2_Step", f"{formatted}.dim")
    output_dir = os.path.join(root, "SLC/3_Stack", formatted)

    print(f"Processing {i+1}/{len(raw_files)}: {fname}")
    start = time.time()
    
    subprocess.run([
        snap_exec,
        graph_path,
        f"-Pinput1={master},{input_dim}",
        f"-Poutput1={output_dir}"
    ], check=True)

    print(f" -> Completed in {(time.time() - start)/60:.2f} min.")

# 2. Rename and sort
def convert_month_to_number(month_str):
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    return month_map.get(month_str, '00')

def sort_and_rename_outputs(root):
    source_dir = os.path.join(root, "SLC/3_Stack")
    target_dir = os.path.join(root, "SLC/3_Stack_sort")
    os.makedirs(target_dir, exist_ok=True)

    start_time = time.time()

    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        if not (filename.endswith(".dim") or filename.endswith(".data")):
            continue

        try:
            parts = filename.split("_")
            year = parts[0]
            month_str = parts[1]
            day = parts[2][:2]
            month = convert_month_to_number(month_str)
            new_basename = f"{year}_{month}_{day}"
        except IndexError:
            print(f"Skipping unrecognized file name: {filename}")
            continue

        new_name = new_basename + (".dim" if filename.endswith(".dim") else ".data")
        new_path = os.path.join(target_dir, new_name)

        if os.path.isfile(file_path):
            shutil.copy2(file_path, new_path)
        elif os.path.isdir(file_path) and not os.path.exists(new_path):
            shutil.copytree(file_path, new_path)

    print(f"Organization completed in {(time.time()-start_time)/60:.1f} minutes")

def remove_iq_files(root):
    data_root = os.path.join(root, "SLC/3_Stack_sort")
    if not os.path.exists(data_root):
        print(f"Directory does not exist: {data_root}")
        return

    removed_files = 0
    start = time.time()

    for folder in os.listdir(data_root):
        if not folder.endswith(".data"):
            continue

        folder_path = os.path.join(data_root, folder)
        for f in os.listdir(folder_path):
            if f.startswith("i_") or f.startswith("q_"):
                try:
                    file_to_remove = os.path.join(folder_path, f)
                    os.remove(file_to_remove)
                    removed_files += 1
                except Exception as e:
                    print(f"Error removing {f}: {e}")

    print(f"Removed {removed_files} i_ and q_ files in {(time.time()-start):.1f} seconds")

# Call in correct order
sort_and_rename_outputs(root)
remove_iq_files(root)

# Optional: delete reference file

def delete_master_dynamically(root):
    """
    Automatically detect master image from January folder and remove it from all other folders (Feb–Dec).
    """
    stack_root = os.path.join(root, "SLC/3_Stack_sort")
    jan_folder = None

    # Step 1: Find January folder
    for folder in os.listdir(stack_root):
        if folder.endswith(".data"):
            try:
                month = int(folder.split("_")[1])
                if month == 1:
                    jan_folder = os.path.join(stack_root, folder)
                    break
            except:
                continue

    if not jan_folder:
        print("January folder not found.")
        return

    # Step 2: Identify master pattern from January folder
    master_stamp = None
    for f in os.listdir(jan_folder):
        if "_mst_" in f and f.endswith(".img"):
            parts = f.split("_mst_")
            if len(parts) > 1:
                master_stamp = parts[1].replace(".img", "")
                break

    if not master_stamp:
        print("Master file not found in January folder.")
        return

    print(f"Identified master file: *_mst_{master_stamp}.[img|hdr]")

    # Step 3: Delete matching master files from other folders (Feb–Dec)
    removed = 0
    skipped = 0
    start = time.time()

    for folder in os.listdir(stack_root):
        if not folder.endswith(".data"):
            continue
        try:
            month = int(folder.split("_")[1])
        except:
            continue

        if month == 1:
            skipped += 1
            continue

        folder_path = os.path.join(stack_root, folder)
        for f in os.listdir(folder_path):
            if f"_mst_{master_stamp}" in f and (f.endswith(".img") or f.endswith(".hdr")):
                file_to_remove = os.path.join(folder_path, f)
                try:
                    os.remove(file_to_remove)
                    removed += 1
                except Exception as e:
                    print(f"Failed to delete {file_to_remove}: {e}")

    duration = time.time() - start
    print(f"Deleted {removed} master files from Feb–Dec in {duration:.1f} sec. Skipped {skipped} January folder(s).")

# Uncomment to run
# root = "/home/cln3/SAR/Sentinel1"  # Or your appropriate root path
# delete_master_dynamically(root)

