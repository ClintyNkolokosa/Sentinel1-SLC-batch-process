# Adapted from https://github.com/Smf566/S1_SNAP_Polsar?tab=readme-ov-file
# Created on 02 May 2025
"############################# Stage 3.1 ###########################################"
" Prepare the directories and the base files to process the images "

library(xml2)

# Timing setup
time_setup <- system.time({
  # Directory setup - matches your folder structure
  base_wd <- "~/SAR/Sentinel1/SLC"
  
  # Input/output directories using file.path to handle slashes
  zip_wd <- file.path(base_wd, "0_Raw_Image")
  graph_wd <- file.path(base_wd, "Base_Graph")
  out_graph_path <- file.path(base_wd, "New_Graph", "Step_1")
  out_hdr_path <- file.path(base_wd, "1_Step")
  
  # Create directories if they don't exist (recursive creates parent dirs if needed)
  dir.create(out_graph_path, showWarnings = FALSE, recursive = TRUE)
  dir.create(out_hdr_path, showWarnings = FALSE, recursive = TRUE)
  
  # Get specific graph file
  graph_a <- file.path(graph_wd, "SLC_preprocess_A.xml")
  if(!file.exists(graph_a)) stop("Graph file not found: ", graph_a)
  
  # Get input zip files
  s1_zip_list <- list.files(zip_wd, pattern = "\\.zip$", full.names = TRUE)
  if(length(s1_zip_list) == 0) stop("No input files found in ", zip_wd)
  
  # Processing parameters
  IW_number <- "IW1"  # Single subswath
  cores_nr <- 4       # Fixed core count
})

"#######################  Step 02 A : SNAP Processing  #######################"

"####################################################"
"Generate Graphs for Each S1 File (within R)"

# Timing graph generation
time_generate_graphs <- system.time({
  library(stringr)
  
  for (file in s1_zip_list) {
    # Read and validate XML
    snap_xml_graph <- read_xml(graph_a)
    
    # Extract date from filename (format: S1A_IW_SLC__1SDV_20240104T...)
    date_str <- str_extract(basename(file), "\\d{8}") %>% 
      as.Date("%Y%m%d")
    
    # Format date as YYYY_Mmm_DD (e.g., 2024_Jan_04)
    original_locale <- Sys.getlocale("LC_TIME")
    Sys.setlocale("LC_TIME", "C")
    formatted_date <- format(date_str, "%Y_%b_%d")
    Sys.setlocale("LC_TIME", original_locale)
    
    # Set input file path
    xml_find_first(snap_xml_graph, "//node[@id='Read']//file") %>% 
      xml_set_text(normalizePath(file))
    
    # Set subswath parameter
    xml_find_first(snap_xml_graph, "//node[@id='TOPSAR-Split']//subswath") %>% 
      xml_set_text(IW_number)
    
    # Set output path (1_Step/YYYY_Mmm_DD.dim)
    output_name <- paste0(formatted_date, ".dim")
    output_path <- file.path(out_hdr_path, output_name)
    # Ensure no double slashes by normalizing the path
    output_path <- normalizePath(output_path, mustWork = FALSE, winslash = "/")
    xml_find_first(snap_xml_graph, "//node[@id='Write']//file") %>% 
      xml_set_text(output_path)
    
    # Save modified graph (New_Graph/Step_1/YYYY_Mmm_DD_stage1.xml)
    graph_name <- paste0(formatted_date, "_stage1.xml")
    write_xml(snap_xml_graph, file.path(out_graph_path, graph_name))
  }
})

"####################################################"
"Batch processing of SNAP graphs"

# Timing batch processing
time_batch_processing <- system.time({
  library(parallelMap)
  error_log <- file.path(base_wd, "processing_errors.log")
  file.create(error_log)
  
  # Get list of generated graphs
  iw_graph_list_new <- list.files(out_graph_path, pattern = "_stage1\\.xml$", full.names = TRUE)
  
  # Process with 5 cores
  parallelStartSocket(cores_nr)
  parallelExport('error_log')
  
  results <- parallelLapply(iw_graph_list_new, function(iw_file_name) {
    tryCatch({
      # Verify graph exists
      if(!file.exists(iw_file_name)) {
        write(paste("Missing graph:", iw_file_name), error_log, append = TRUE)
        return(FALSE)
      }
      
      # Run with increased memory
      cmd <- paste0("/home/cln3/esa-snap/bin/gpt -J-Xmx24G -q 1 \"", iw_file_name, "\"")
      exit_code <- system(cmd)
      
      if(exit_code != 0) {
        write(paste("Failed with code", exit_code, ":", iw_file_name), 
              error_log, append = TRUE)
        return(FALSE)
      }
      return(TRUE)
    }, error = function(e) {
      write(paste("Error:", iw_file_name, "-", e$message), error_log, append = TRUE)
      return(FALSE)
    })
  })
  
  parallelStop()
  gc()
  
  # Report results
  success_count <- sum(unlist(results))
  cat("\nSuccessfully processed", success_count, "of", length(iw_graph_list_new), "files")
})

"############################## Timing Results ##################################"
cat("\nProcessing Summary:")
cat("\n-------------------------------------")
cat("\nInitial setup:", round(time_setup["elapsed"], 2), "seconds")
cat("\nGraph generation:", round(time_generate_graphs["elapsed"], 2), "seconds")
cat("\nBatch processing:", round(time_batch_processing["elapsed"], 2), "seconds")
cat("\nTotal time:", round(sum(time_setup["elapsed"], 
                               time_generate_graphs["elapsed"], 
                               time_batch_processing["elapsed"]), 2), "seconds\n")

# Verify outputs
output_files <- list.files(out_hdr_path, pattern = "\\.dim$")
if(length(output_files) > 0) {
  cat("\nGenerated outputs in 1_Step/:")
  cat("\n", paste(output_files, collapse = "\n "))
} else {
  cat("\nNo outputs generated! Check error log:", error_log)
}

