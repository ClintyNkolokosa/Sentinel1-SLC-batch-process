############################# Stage 3.2 ###########################################
# Process intermediate files from Step 1 using SLC_preprocess_B.xml

# Load required packages
library(xml2)
library(parallel)
library(stringr)
library(pbapply)
library(future)      # NEW: For async processing
library(future.apply) # NEW: For parallel graph generation

# Initialize async
plan(multisession)   # Non-blocking background sessions

# Timing setup
time_setup_stage2 <- Sys.time()

# Directory setup
base_wd <- normalizePath("~/SAR/Sentinel1/SLC/", mustWork = TRUE)

# Input/output directories
step1_dir <- file.path(base_wd, "1_Step/")
graph_wd <- file.path(base_wd, "Base_Graph/")
out_graph_path <- file.path(base_wd, "New_Graph/Step_2/")
processed_dir <- file.path(base_wd, "2_Step/")

# Create directories if they don't exist
dir.create(out_graph_path, showWarnings = FALSE, recursive = TRUE)
dir.create(processed_dir, showWarnings = FALSE, recursive = TRUE)

# Get specific graph file
graph_b <- normalizePath(file.path(graph_wd, "SLC_preprocess_B.xml"), mustWork = TRUE)
if (!file.exists(graph_b)) stop("Graph file not found: ", graph_b)

# Get input dim files from Step 1
input_files <- list.files(step1_dir, pattern = "\\.dim$", full.names = TRUE, recursive = TRUE)
if (length(input_files) == 0) stop("No input files found in ", step1_dir)

# Processing parameters
cores_nr <- 3
mem_per_core <- "24G"
error_log <- file.path(base_wd, "processing_errors_stage2.log")
file.create(error_log)

cat("####################### Step 02 B : SNAP Processing #######################\n")

# Generate Stage 2 Graphs ASYNCHRONOUSLY (Optimization 6)
cat("Generating Stage 2 Graphs in parallel...\n")
start_graph <- Sys.time()

# Parallel graph generation
generate_graph <- function(input_file) {
  tryCatch({
    snap_xml_graph <- read_xml(graph_b)
    date_str <- tools::file_path_sans_ext(basename(input_file))
    
    xml_find_first(snap_xml_graph, "//node[@id='Read']//file") |> 
      xml_set_text(normalizePath(input_file))
    
    output_name <- paste0(date_str, ".dim")
    output_path <- normalizePath(file.path(processed_dir, output_name), mustWork = FALSE)
    xml_find_first(snap_xml_graph, "//node[@id='Write']//file") |> 
      xml_set_text(output_path)
    
    graph_name <- paste0(date_str, "_stage2.xml")
    write_xml(snap_xml_graph, file.path(out_graph_path, graph_name))
    
    return(TRUE)
  }, error = function(e) {
    write(paste(Sys.time(), "Graph Error:", e$message), error_log, append = TRUE)
    return(FALSE)
  })
}

# Generate graphs async while preparing processing
graph_future <- future(
  future_lapply(input_files, generate_graph, future.seed = TRUE)
)

# Batch Processing with I/O Priority (Optimization 7)
cat("\nStarting Batch Processing with ionice...\n")
start_batch <- Sys.time()

stage2_graphs <- list.files(out_graph_path, pattern = "_stage2\\.xml$", full.names = TRUE)
while (length(stage2_graphs) == 0) {  # Wait for first graphs
  Sys.sleep(5)
  stage2_graphs <- list.files(out_graph_path, pattern = "_stage2\\.xml$", full.names = TRUE)
}

cl <- makeCluster(cores_nr, outfile = error_log)
on.exit({
  try(stopCluster(cl), silent = TRUE)
  try(closeAllConnections(), silent = TRUE)
  gc()
})

clusterExport(cl, c("error_log", "mem_per_core", "processed_dir"))
clusterEvalQ(cl, {
  library(xml2)
  Sys.setenv(JAVA_HOME = "/usr/lib/jvm/java-8-openjdk-amd64")
})

results <- pblapply(stage2_graphs, cl = cl, FUN = function(graph_file) {
  tryCatch({
    output_file <- xml_find_first(read_xml(graph_file), "//node[@id='Write']//file") |> xml_text()
    data_dir <- paste0(tools::file_path_sans_ext(output_file), ".data")
    
    # Clean previous outputs
    suppressWarnings({
      if (file.exists(output_file)) file.remove(output_file)
      if (dir.exists(data_dir)) unlink(data_dir, recursive = TRUE)
    })
    
    # I/O Priority (Optimization 7)
    process_log <- paste0(tools::file_path_sans_ext(graph_file), ".process.log")
    cmd <- sprintf(
      "ionice -c2 -n0 /home/cln3/esa-snap/bin/gpt -J-Xmx%s -q 1 -e \"%s\" >%s 2>&1",
      mem_per_core, graph_file, process_log
    )
    
    exit_code <- system(cmd, timeout = 3600)
    success <- file.exists(output_file) && dir.exists(data_dir) && exit_code == 0
    
    if (!success) {
      error_msg <- c(paste("Failed:", basename(graph_file)),
                     paste("Exit code:", exit_code),
                     paste("Log:", process_log))
      write(error_msg, error_log, append = TRUE)
    }
    
    return(success)
  }, error = function(e) {
    write(paste("Worker Error:", e$message), error_log, append = TRUE)
    return(FALSE)
  })
})

# Finalize async
while (!resolved(graph_future)) Sys.sleep(1)  # Ensure all graphs generated

end_batch <- Sys.time()
cat("\nBatch processing took", round(difftime(end_batch, start_batch, units = "secs"), 1), "seconds\n")

# Results summary
success_count <- sum(unlist(results))
failed_count <- length(stage2_graphs) - success_count

cat("\nStage 2 Results:")
cat("\n-------------------------------------")
cat("\nTotal processed:", length(stage2_graphs))
cat("\nSuccess:", success_count)
cat("\nFailed:", failed_count)
if (failed_count > 0) cat("\nCheck logs:", error_log)
