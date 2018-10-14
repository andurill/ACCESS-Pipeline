#! /usr/bin/env Rscript

##################################################
# Innovation Laboratory
# Center For Molecular Oncology
# Memorial Sloan Kettering Cancer Research Center
# Maintainer: Ian Johnson (johnsoni@mskcc.org)
##################################################

library(grid)
library(yaml)
library(tidyr)
library(scales)
library(gridBase)
library(gridExtra)
library(lattice)
library(ggplot2)
library(reshape2)
library('getopt');
library(data.table)

suppressMessages(library(dplyr))

#' Todo: Turn these scripts into a proper R package
source_local <- function(fname){
  argv <- commandArgs(trailingOnly = FALSE)
  base_dir <- dirname(substring(argv[grep("--file=", argv)], 8))
  source(paste(base_dir, fname, sep="/"))
}

source_local('plots.r')
source_local('util.r')
source_local('constants.r')


#' Print the title file to our PDF
#' @param title_df title file sample info data frame
#' @param coverage_df coverage values data frame
#' @param inputs_yaml pipeline inputs file
print_title = function(title_df, coverage_df, inputs_yaml) {
  # Define the output PDF file
  pdf(file = 'title_page.pdf', height=15, width=18, onefile=TRUE)
  
  # Round to one decimal place
  coverage_df$average_coverage = format(round(coverage_df$average_coverage, 1), nsmall = 1)
  
  # Cast the coverage values
  coverage_df = dcast(
    coverage_df,
    as.formula(paste(SAMPLE_ID_COLUMN, "~ method + pool")),
    value.var='average_coverage'
  )
  
  # Select relevant coverage columns
  selected_cols = c(
    SAMPLE_ID_COLUMN, 
    'TotalCoverage_A Targets',
    'TotalCoverage_B Targets',
    'Duplex_A Targets'
  )
  coverage_df = coverage_df[, selected_cols]
  
  # Rename coverage columns
  colnames(coverage_df) = c(
    SAMPLE_ID_COLUMN,
    'RawCoverage_A',
    'RawCoverage_B',
    'DuplexCoverage_A'
  )
  
  title = textGrob(label = 'MSK-ACCESS QC Report', gp=gpar(fontsize=22, col='black'))
  project_name = textGrob(inputs_yaml$project_name, gp=gpar(fontsize=20, col='black'))
  date = textGrob(format(Sys.time(), '%a %b %d, %Y %H:%M'), gp=gpar(fontsize=20, col='black'))
  version = textGrob(paste('Pipeline Version: ', inputs_yaml$version), gp=gpar(fontsize=20, col='black'))
  line = linesGrob(unit(c(0.05, 0.95), 'npc'), unit(1, 'npc'), gp=gpar(col='lightgrey', lwd=4))
  
  # Merge in coverage data
  title_df = inner_join(title_df, coverage_df, by=paste(SAMPLE_ID_COLUMN))
  # Remove some columns
  title_df = title_df[, !(names(title_df) %in% DROP_COLS)]
  # Convert to grob
  title_grob <- tableGrob(title_df, rows=NULL, theme=TITLE_PAGE_THEME)
  
  # Arrange grobs
  lay <- matrix(c(1,2,3,4,5,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6), byrow=TRUE)
  gs = list(title, project_name, date, version, line, title_grob)
  grid.arrange(grobs=gs, layout_matrix=lay)
  
  dev.off()
}


#' Print the input files and run parameters to the current device
#' @param inputs_yaml yaml file with inputs to pipeline
print_inputs <- function(inputs_yaml) {
  # Define the output PDF file
  pdf(file = 'pipeline_inputs.pdf', height = 26, width = 8, onefile = TRUE)
  
  inputs_theme = ttheme_default(
    core = list(fg_params = list(hjust = 0, x = 0.05)),
    rowhead = list(fg_params  = list(hjust = 0, x = 0)),
    base_size = 5,
    base_colour = 'black',
    base_family = '',
    parse = FALSE,
    padding = unit(c(4, 2), 'mm'))
  
  mat = matrix(ncol=2)
  for (name in names(inputs_yaml)) {
    value = unlist(inputs_yaml[[name]])
    value = gsub(',', '\n', toString(value))
    value = gsub('File\n', '', value)
    mat = rbind(mat, c(toString(name), value))
  }
  grid.table(mat, theme = inputs_theme)
  
  dev.off()
}


#' Read in all tables for plots
#' @param inDirTables location of tables from python tables_module
read_tables = function(inDirTables, family_types_A_path, family_types_B_path, family_sizes_path) {
  readCountsDataTotal = read.table(paste(inDirTables, 'read-counts-total.txt', sep='/'), sep='\t', head=TRUE)
  covPerInterval = read.table(paste(inDirTables, 'coverage-per-interval.txt', sep='/'), sep='\t', head=TRUE)
  insertSizes = read.table(paste(inDirTables, 'fragment-sizes.txt', sep='/'), sep='\t', head=TRUE)
  meanCovData = read.table(paste(inDirTables, 'coverage-agg.txt', sep='/'), sep='\t', head=TRUE)
  gcEachSample = read.table(paste(inDirTables, 'GC-bias-with-coverage-averages-over-each-sample.txt', sep='/'), sep='\t', head=TRUE)
  
  family_types_A = read.table(family_types_A_path, sep = '\t', header = TRUE, colClasses = c('character', 'character', 'numeric'))
  family_types_B = read.table(family_types_B_path, sep = '\t', header = TRUE, colClasses = c('character', 'character', 'numeric'))
  families = read.table(family_sizes_path, sep = '\t', header = TRUE, colClasses = c('numeric', 'character', 'numeric', 'character'))
  
  list(readCountsDataTotal, covPerInterval, insertSizes, meanCovData, gcEachSample, family_types_A, family_types_B, families)
}


#' Main entry point
main = function() {
  # Read arguments specifying table paths and output location
  args = read_inputs()
  tables_output_dir = args$tables_output_dir
  title_file_path = args$title_file_path
  family_types_A_path = args$family_types_A_path
  family_types_B_path = args$family_types_B_path
  family_sizes_path = args$family_sizes_path
  # Load our pipeline inputs file for printing (and convert integers to strings)
  inputs_yaml = yaml.load_file(args$inputs_yaml_path, handlers = list('int' = toString))

  # Read title file
  # (careful with "Sex" column, R will try to coerce column of all "F" to logical)
  title_df = read.table(
    title_file_path, 
    sep = '\t', 
    header = TRUE, 
    colClasses = c('SEX' = 'character')
  )
  print('Title dataframe:')
  print(title_df)
  
  # Title file sample colunn is used as sort order
  sort_order = as.character(unlist(title_df[SAMPLE_ID_COLUMN]))
  print('Sample Sort Order:')
  print(sort_order)
  
  # Read in tables
  df_list = read_tables(tables_output_dir, family_types_A_path, family_types_B_path, family_sizes_path)
  print('Dataframes 0:')
  lapply(df_list, function(x) {print(head(x))})
  # Fix sample names
  df_list = lapply(df_list, cleanup_sample_names, sort_order)
  print("Dataframes 1:")
  lapply(df_list, function(x) {print(head(x))})
  # Merge in the title file data by sample id
  df_list = lapply(df_list, merge_in_title_file_data, title_df)
  print('Dataframes 2:')
  lapply(df_list, function(x) {print(head(x))})
  # Sort by sample class
  df_list = lapply(df_list, sort_df, paste(TITLE_FILE__SAMPLE_CLASS_COLUMN))
  print('Dataframes 3:')
  lapply(df_list, function(x) {print(head(x))})
  
  # Now that we've sorted in the order we want,
  # make the Sample column a factor in that order as well 
  # (ggplot uses the X axis sort order if it is a factor)
  df_list = lapply(df_list, function(df){ 
    df[, SAMPLE_ID_COLUMN] = factor(df[, SAMPLE_ID_COLUMN], levels = unique(df[, SAMPLE_ID_COLUMN])) 
    df
  })
  
  # We have had problems here with sample names not matching between metrics files and title_file entries
  print('Dataframes after processing:')
  lapply(df_list, function(x) {print(head(x))})
  
  read_counts_data = df_list[[1]]
  cov_per_interval = df_list[[2]]
  insert_sizes = df_list[[3]]
  mean_cov_data = df_list[[4]]
  gc_each_sample = df_list[[5]]
  family_types_A = df_list[[6]]
  family_types_B = df_list[[7]]
  families = df_list[[8]]
  
  # Print PDFs
  print_title(title_df, mean_cov_data, inputs_yaml)
  plot_read_pairs_count(read_counts_data)
  plot_align_genome(read_counts_data)
  plot_on_bait(read_counts_data)
  plot_insert_size_distribution(insert_sizes)
  plot_cov_dist_per_interval_line(cov_per_interval)
  plot_mean_cov(mean_cov_data)
  plot_gc_with_cov_each_sample(gc_each_sample, sort_order)
  plot_family_types(family_types_A, family_types_B)
  plot_family_curves(families)
  
  # Print the inputs and parameters
  print_inputs(inputs_yaml)
}


# Run main()
main()
# Show warnings after running
warnings()
