#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 10 12:01:52 2025

@author: cln3
"""


import os
from datetime import date
from pathlib import Path
import asf_search as asf
import geopandas as gpd
from shapely.geometry import box
from tqdm import tqdm  # For progress tracking

#============================================
print("Current Working Directory:", os.getcwd())

# Create directories if they don't exist
# dirs = ['Downloads']
# for d in dirs:
#     Path(d).mkdir(exist_ok=True)
    
print(os.listdir(os.getcwd()))

#==============================================
# Shapefile for AOI
gdf = gpd.read_file('/home/cln3/SAR/aoi.shp')

# Extract bounding box coordinates
bounds = gdf.total_bounds
print("Bounding Box:", bounds)

# Create GeoDataFrame of bbox
gdf_bounds = gpd.GeoSeries([box(*bounds)])
print("Bounding Box Geometry:", gdf_bounds)

# Convert to WKT for ASF search
wkt_aoi = gdf_bounds.to_wkt().values.tolist()[0]

#==================================================
# Search query for Sentinel-1 SLC/GRD data
# Filter by the specific orbit
print("Searching for Sentinel-1 images...")

#from asf_search import ASFSearchOptions
#help(ASFSearchOptions)

results = asf.search(
    platform=asf.PLATFORM.SENTINEL1,
    processingLevel=[asf.PRODUCT_TYPE.SLC],
    relativeOrbit=[79],
    start=date(2023, 1, 1),
    end=date(2023, 12, 31),
    intersectsWith = wkt_aoi)

# results = asf.search(
#     platform=asf.PLATFORM.SENTINEL1,
#     processingLevel=[asf.PRODUCT_TYPE.GRD_HD], 
#     relativeOrbit=[79],
#     start=date(2025, 1, 1),
#     end=date(2025, 4, 30),
#     intersectsWith=wkt_aoi)

print(f"Total images found: {len(results)}")

# Save metadata if needed
metadata = results.geojson()

#==================================================
# Authenticate session
session = asf.ASFSession().auth_with_creds('nkolokosa72', 'hTT37&t?:zHAtsJ')

#=================================================
# Download images with progress tracking

download_path = '/home/cln3/SAR/Sentinel1/SLC/0_Raw_Image/'

print(f"Downloading {len(results)} images to {download_path}...")

# Use tqdm to track progress
with tqdm(total=len(results), desc="Downloading", unit="file") as pbar:
    for product in results:
        try:
            product.download(path=download_path, session=session)  # Removed 'processes'
            pbar.update(1)  # Update progress bar after each download
        except Exception as e:
            print(f"Error downloading {product.properties['fileID']}: {e}")

print("Download completed.")
