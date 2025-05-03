using Dates
using Glob
using XMLDict
using Distributed
using Logging
using Printf

# Constants
const BASE_DIR = expanduser("~/SAR/Sentinel1/SLC")
const ZIP_DIR = joinpath(BASE_DIR, "0_Raw_Image")
const GRAPH_DIR = joinpath(BASE_DIR, "Base_Graph")
const OUT_GRAPH_DIR = joinpath(BASE_DIR, "New_Graph", "Step_1")
const OUT_HDR_DIR = joinpath(BASE_DIR, "1_Step")
const IW_NUMBER = "IW1"
const CORES = min(4, Sys.CPU_THREADS)
const SNAP_BIN = "/home/cln3/esa-snap/bin/gpt"
const MEMORY_PER_CORE = "24G"
const LOG_FILE = joinpath(BASE_DIR, "processing_errors.log")

# Stage 2 Constants
const STAGE2_GRAPH = joinpath(BASE_DIR, "Base_Graph", "SLC_preprocess_B.xml")
const STAGE2_OUT_GRAPH_DIR = joinpath(BASE_DIR, "New_Graph", "Step_2")
const PROCESSED_DIR = joinpath(BASE_DIR, "2_Step")

function setup_logging()
    logger = SimpleLogger(open(LOG_FILE, "w"))
    global_logger(logger)
end

function create_directories()
    for dir in [OUT_GRAPH_DIR, OUT_HDR_DIR, STAGE2_OUT_GRAPH_DIR, PROCESSED_DIR]
        isdir(dir) || mkpath(dir)
    end
end

function get_input_files()
    files = glob("*.zip", ZIP_DIR)
    isempty(files) && error("No input files found in $ZIP_DIR")
    return files
end

function format_date_from_filename(filename)
    m = match(r"\d{8}", filename)
    m === nothing && error("Could not extract date from filename: $filename")
    
    date_str = m.match
    date_obj = Date(date_str, "yyyymmdd")
    
    # Format as YYYY_Mmm_DD
    return Dates.format(date_obj, "YYYY_uuu_dd")
end

function load_template(template_path)
    !isfile(template_path) && error("Template not found: $template_path")
    return xml_dict(template_path)
end

function modify_template!(template, input_file, output_name, subswath)
    # Set input file path
    for node in get(template["graph"], "node", [])
        if get(node, "@id", "") == "Read"
            node["parameters"]["file"] = abspath(input_file)
        end
    end
    
    # Set subswath parameter
    for node in get(template["graph"], "node", [])
        if get(node, "@id", "") == "TOPSAR-Split"
            node["parameters"]["subswath"] = subswath
        end
    end
    
    # Set output path
    output_path = joinpath(OUT_HDR_DIR, output_name * ".dim")
    for node in get(template["graph"], "node", [])
        if get(node, "@id", "") == "Write"
            node["parameters"]["file"] = abspath(output_path)
        end
    end
    return template
end

function generate_graphs(input_files, template_path, output_graph_dir)
    template = load_template(template_path)
    success_count = 0
    
    @sync for file in input_files
        @async begin
            try
                formatted_date = format_date_from_filename(basename(file))
                output_name = formatted_date * ".dim"
                graph_name = formatted_date * "_stage1.xml"
                
                # Create a deep copy of the template
                local_template = deepcopy(template)
                modified_template = modify_template!(local_template, file, formatted_date, IW_NUMBER)
                
                # Write the modified graph
                graph_path = joinpath(output_graph_dir, graph_name)
                open(graph_path, "w") do io
                    print(io, xml_dict_to_string(modified_template))
                end
                
                success_count += 1
            catch e
                @error "Graph generation failed for $file" exception=(e, catch_backtrace())
            end
        end
    end
    
    return success_count
end

function process_graph(graph_file, output_dir)
    try
        output_file = joinpath(output_dir, replace(basename(graph_file), "_stage1.xml" => ".dim")
        data_dir = splitext(output_file)[1] * ".data"
        
        # Clean existing outputs
        isfile(output_file) && rm(output_file)
        isdir(data_dir) && rm(data_dir, recursive=true)
        
        # Build and run command
        cmd = `$SNAP_BIN -J-Xmx$MEMORY_PER_CORE -q 1 -c 2048M --openmp $CORES $graph_file`
        run(pipeline(cmd, stdout=devnull, stderr=devnull))
        
        return isfile(output_file) && isdir(data_dir)
    catch e
        @error "Processing failed for $graph_file" exception=(e, catch_backtrace())
        return false
    end
end

function process_graphs(graph_files, output_dir)
    success_count = 0
    
    if length(graph_files) > 1 && CORES > 1
        # Parallel processing
        @sync for chunk in Iterators.partition(graph_files, ceil(Int, length(graph_files)/CORES))
            @async begin
                for graph in chunk
                    process_graph(graph, output_dir) && (success_count += 1)
                end
            end
        end
    else
        # Sequential processing
        for graph in graph_files
            process_graph(graph, output_dir) && (success_count += 1)
        end
    end
    
    return success_count
end

function process_stage1()
    println("############################# Stage 3.1 ###########################################")
    start_time = time()
    
    setup_logging()
    create_directories()
    
    try
        zip_files = get_input_files()
        println("\nFound $(length(zip_files)) input files")
        
        # Generate graphs
        println("Generating Stage 1 Graphs...")
        graph_start = time()
        success_count = generate_graphs(zip_files, joinpath(GRAPH_DIR, "SLC_preprocess_A.xml"), OUT_GRAPH_DIR)
        graph_time = time() - graph_start
        @printf "Generated %d graphs in %.2f seconds\n" success_count graph_time
        
        # Process graphs
        println("\nProcessing graphs with SNAP...")
        process_start = time()
        graph_files = glob("*_stage1.xml", OUT_GRAPH_DIR)
        processed_count = process_graphs(graph_files, OUT_HDR_DIR)
        process_time = time() - process_start
        
        # Results
        total_time = time() - start_time
        println("\nProcessing Summary:")
        println("-------------------------------------")
        @printf "Graph generation: %.2f seconds\n" graph_time
        @printf "SNAP processing: %.2f seconds\n" process_time
        @printf "Total time: %.2f minutes\n" total_time/60
        @printf "\nSuccessfully processed %d of %d files\n" processed_count length(graph_files)
        
        # Output verification
        output_files = glob("*.dim", OUT_HDR_DIR)
        if !isempty(output_files)
            println("\nGenerated $(length(output_files)) outputs in $OUT_HDR_DIR")
        else
            println("\nNo outputs generated! Check error log: $LOG_FILE")
        end
        
    catch e
        @error "Stage 1 failed" exception=(e, catch_backtrace())
        rethrow()
    end
end

function process_stage2()
    println("\n############################# Stage 3.2 ###########################################")
    start_time = time()
    
    try
        input_files = glob("*.dim", OUT_HDR_DIR)
        isempty(input_files) && error("No input files found in $OUT_HDR_DIR")
        
        println("\nFound $(length(input_files)) input files for Stage 2")
        
        # Generate Stage 2 graphs
        println("Generating Stage 2 Graphs...")
        graph_start = time()
        success_count = generate_graphs(input_files, STAGE2_GRAPH, STAGE2_OUT_GRAPH_DIR)
        graph_time = time() - graph_start
        @printf "Generated %d graphs in %.2f seconds\n" success_count graph_time
        
        # Process Stage 2 graphs
        println("\nProcessing Stage 2 graphs with SNAP...")
        process_start = time()
        stage2_graphs = glob("*_stage2.xml", STAGE2_OUT_GRAPH_DIR)
        processed_count = process_graphs(stage2_graphs, PROCESSED_DIR)
        process_time = time() - process_start
        
        # Results
        total_time = time() - start_time
        println("\nStage 2 Processing Summary:")
        println("-------------------------------------")
        @printf "Graph generation: %.2f seconds\n" graph_time
        @printf "SNAP processing: %.2f seconds\n" process_time
        @printf "Total time: %.2f minutes\n" total_time/60
        @printf "\nSuccessfully processed %d of %d files\n" processed_count length(stage2_graphs)
        
    catch e
        @error "Stage 2 failed" exception=(e, catch_backtrace())
        rethrow()
    end
end

# Main execution
try
    process_stage1()
    process_stage2()
catch e
    @error "Fatal error" exception=(e, catch_backtrace())
    exit(1)
end
