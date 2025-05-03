#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modified to properly handle pre_pro.py output files
"""
import sys
import glob
import subprocess
import os
import shutil
import time
import configparser
from datetime import datetime
import logging

# Add SAR directory to Python path
sys.path.insert(0, '/home/cln3/SAR/')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Month mapping for consistent English abbreviations
MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def load_config(config_file_path):
    """Load configuration parameters from config file."""
    parser = configparser.ConfigParser()
    parser.read(config_file_path)
    config = {
        "root": parser.get("SoilMoistureMapping_config", "root"),
        "graph_path_2": parser.get("SoilMoistureMapping_config", "graph_path_2"),
        "SNAP_version_2": parser.get("SoilMoistureMapping_config", "SNAP_version_2")
    }
    return config

def convert_month_to_number(month_str):
    """Convert month abbreviation to number (e.g., 'Apr' -> '04')."""
    month_map = {abbr: f"{i:02d}" for i, abbr in enumerate(MONTH_ABBR, 1)}
    return month_map.get(month_str, '00')

def get_date_from_filename(filename):
    """Extract date from pre_pro.py output filename (YYYY_Mmm_DD.dim)"""
    try:
        base_name = os.path.basename(filename)
        if not base_name.endswith('.dim'):
            return None
        
        # Handle both formats: original S1A... names and YYYY_Mmm_DD names
        if base_name.startswith('S1'):
            # Original format: S1A_IW_GRDH_1SDV_20181107T031553_20181107T031618_024476_02AEFD_741A_TC.dim
            date_str = base_name.split('_')[5][:8]  # Get YYYYMMDD from timestamp
            return datetime.strptime(date_str, "%Y%m%d")
        else:
            # New format: YYYY_Mmm_DD.dim
            date_part = base_name[:11]  # First 11 characters (YYYY_Mmm_DD)
            return datetime.strptime(date_part, "%Y_%b_%d")
    except Exception as e:
        logging.error(f"Error parsing date from filename {filename}: {e}")
        return None

def process_images(config):
    """Process Sentinel-1 GRD images using SNAP."""
    root = config["root"]
    processed_dir = os.path.join(root, 'Sentinel1/1_Processed_Image')
    
    # Get all processed .dim files
    processed_files = glob.glob(os.path.join(processed_dir, '*.dim'))
    if not processed_files:
        logging.error(f"No processed .dim files found in {processed_dir}")
        return
    
    # Create a list of tuples (datetime, filepath) for sorting
    dated_files = []
    for f in processed_files:
        file_date = get_date_from_filename(f)
        if file_date:
            dated_files.append((file_date, f))
    
    if not dated_files:
        logging.error("No valid dated files found")
        return
    
    # Sort by date
    dated_files.sort()
    
    # Use earliest file as master
    master_date, master_path = dated_files[0]
    logging.info(f"Using master file from {master_date.strftime('%Y-%b-%d')}: {os.path.basename(master_path)}")
    
    # Process all files
    for i, (file_date, img_path) in enumerate(dated_files, 1):
        try:
            # Create output directory based on date
            month_abbr = MONTH_ABBR[file_date.month - 1]
            formatted_date = f"{file_date.year}_{month_abbr}_{file_date.day:02d}"
            stack_out_path = os.path.join(root, 'Sentinel1/2_GRD_Stack', formatted_date)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(stack_out_path), exist_ok=True)
            
            logging.info(f'Processing {i}/{len(dated_files)}: {os.path.basename(img_path)}')
            
            # Run SNAP processing
            tic = time.time()
            subprocess.call([
                config["SNAP_version_2"],
                config["graph_path_2"],
                f'-Pinput1={master_path},{img_path}',
                f'-Poutput1={stack_out_path}'
            ])
            toc = time.time()
            logging.info(f'Processing took {(toc-tic)/60:.2f} min.')
            
        except Exception as e:
            logging.error(f"Failed to process {img_path}: {e}")

def sort_files_snap(path_pre, path):
    """Sort and rename processed files."""
    # Get all .data directories
    data_dirs = [d for d in sorted(os.listdir(path_pre)) if d.endswith('.data')]
    
    # Create output directory if it doesn't exist
    os.makedirs(path, exist_ok=True)
    
    for data_dir in data_dirs:
        original_name = data_dir[:-5]  # Remove '.data' extension
        from_directory = os.path.join(path_pre, data_dir)
        
        try:
            # Split directory name into components (format: YYYY_Mmm_DD)
            parts = original_name.split('_')
            if len(parts) != 3:
                raise ValueError(f"Invalid directory name format: {original_name}")
            
            year, month_abbr, day = parts
            
            # Validate day component
            if not day.isdigit() or len(day) != 2:
                raise ValueError(f"Invalid day format: {day}")
            
            # Convert month abbreviation to number
            month_num = convert_month_to_number(month_abbr)
            if month_num == '00':
                raise ValueError(f"Invalid month abbreviation: {month_abbr}")
            
            # Create new folder name
            new_folder_name = f"{year}_{month_num}_{day}"
            to_directory = os.path.join(path, new_folder_name)
            
            # Remove existing directory if present
            if os.path.exists(to_directory):
                shutil.rmtree(to_directory)
            
            # Copy the directory
            shutil.copytree(from_directory, to_directory)
            logging.info(f"Successfully processed: {original_name} -> {new_folder_name}")
            
        except (ValueError, IndexError) as e:
            logging.error(f"Skipping {original_name}: {str(e)}")
            continue
        except Exception as e:
            logging.error(f"Error processing {original_name}: {str(e)}")
            continue
    
    return [d[:-5] for d in data_dirs]

def main():
    config_file_path = "/home/cln3/SAR/config.txt"
    config = load_config(config_file_path)
    
    # Process images
    process_images(config)
    
    # Sort and rename files
    path_pre = os.path.join(config["root"], "Sentinel1/2_GRD_Stack/")
    path = os.path.join(config["root"], "Sentinel1/3_GRD_Stack_Sorted/")
    list_dates = sort_files_snap(path_pre, path)
    logging.info("Processing complete. Sorted dates: %s", list_dates)

if __name__ == "__main__":
    main()