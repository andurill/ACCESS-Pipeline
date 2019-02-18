cwlVersion: v1.0

class: Workflow

requirements:
  MultipleInputFeatureRequirement: {}
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}
  SchemaDefRequirement:
    types:
      - $import: ../resources/run_tools/schemas.yaml
      - $import: ../resources/run_params/schemas/process_loop_umi_fastq.yaml
      - $import: ../resources/run_params/schemas/trimgalore.yaml
      - $import: ../resources/run_params/schemas/add_or_replace_read_groups.yaml
      - $import: ../resources/run_params/schemas/mark_duplicates.yaml
      - $import: ../resources/run_params/schemas/find_covered_intervals.yaml
      - $import: ../resources/run_params/schemas/abra.yaml
      - $import: ../resources/run_params/schemas/fix_mate_information.yaml
      - $import: ../resources/run_params/schemas/base_recalibrator.yaml
      - $import: ../resources/run_params/schemas/print_reads.yaml
      - $import: ../resources/run_params/schemas/marianas_collapsing.yaml
      - $import: ../resources/run_params/schemas/waltz.yaml

inputs:

  tmp_dir: string
  run_tools: ../resources/run_tools/schemas.yaml#run_tools

  title_file: File
  inputs_yaml: File
  # Todo: These need to exist in the inputs.yaml,
  # so they need to exist here, but they aren't used
  project_name: string
  version: string

  fastq1: File[]
  fastq2: File[]
  sample_sheet: File[]
  patient_id: string[]
  adapter: string[]
  adapter2: string[]
  add_rg_LB: int[]
  add_rg_ID: string[]
  add_rg_PU: string[]
  add_rg_SM: string[]

  # Todo: Open a ticket
  # bwa cannot read symlink for the fasta.fai file?
  # so we need to use strings here instead of file types
  reference_fasta: string
  reference_fasta_fai: string

  process_loop_umi_fastq__params: ../resources/run_params/schemas/process_loop_umi_fastq.yaml#process_loop_umi_fastq__params
  trimgalore__params: ../resources/run_params/schemas/trimgalore.yaml#trimgalore__params
  add_or_replace_read_groups__params: ../resources/run_params/schemas/add_or_replace_read_groups.yaml#add_or_replace_read_groups__params
  mark_duplicates__params: ../resources/run_params/schemas/mark_duplicates.yaml#mark_duplicates__params
  find_covered_intervals__params: ../resources/run_params/schemas/find_covered_intervals.yaml#find_covered_intervals__params
  abra__params: ../resources/run_params/schemas/abra.yaml#abra__params
  fix_mate_information__params: ../resources/run_params/schemas/fix_mate_information.yaml#fix_mate_information__params
  base_recalibrator__params: ../resources/run_params/schemas/base_recalibrator.yaml#base_recalibrator__params
  print_reads__params: ../resources/run_params/schemas/print_reads.yaml#print_reads__params
  marianas_collapsing__params: ../resources/run_params/schemas/marianas_collapsing.yaml#marianas_collapsing__params
  waltz__params: ../resources/run_params/schemas/waltz.yaml#waltz__params

  bqsr__knownSites_dbSNP: File
  bqsr__knownSites_millis: File

  fci_2__basq_fix: boolean?
  pool_a_bed_file: File
  pool_b_bed_file: File
  A_on_target_positions: File
  B_on_target_positions: File
  noise__good_positions_A: File
  gene_list: File
  FP_config_file: File

outputs:

  clipping_info:
    type: File[]
    outputSource: standard_bam_generation/clipping_info

  clstats1:
    type: File[]
    outputSource: standard_bam_generation/clstats1

  clstats2:
    type: File[]
    outputSource: standard_bam_generation/clstats2

  md_metrics:
    type: File[]
    outputSource: standard_bam_generation/md_metrics

  fci_covint_list:
    type: File[]
    outputSource: standard_bam_generation/covint_list

  fci_covint_bed:
    type: File[]
    outputSource: standard_bam_generation/covint_bed

  bam_dirs:
    type: Directory[]
    outputSource: standard_bam_to_collapsed_qc/bam_dirs

  combined_qc:
    type: Directory
    outputSource: standard_bam_to_collapsed_qc/combined_qc

  qc_tables:
    type: Directory
    outputSource: standard_bam_to_collapsed_qc/qc_tables

steps:

  #####################
  # Generate Std Bams #
  #####################

- id: standard_bam_generation
  run: ./standard_pipeline.cwl
  in:
    run_tools: run_tools
    fastq1: fastq1
    fastq2: fastq2
    sample_sheet: sample_sheet
    tmp_dir: tmp_dir
    reference_fasta: reference_fasta
    reference_fasta_fai: reference_fasta_fai
    patient_id: patient_id
    adapter: adapter
    adapter2: adapter2

    add_rg_LB: add_rg_LB
    add_rg_ID: add_rg_ID
    add_rg_PU: add_rg_PU
    add_rg_SM: add_rg_SM

    bqsr__knownSites_dbSNP: bqsr__knownSites_dbSNP
    bqsr__knownSites_millis: bqsr__knownSites_millis

    process_loop_umi_fastq__params: process_loop_umi_fastq__params
    trimgalore__params: trimgalore__params
    add_or_replace_read_groups__params: add_or_replace_read_groups__params
    mark_duplicates__params: mark_duplicates__params
    find_covered_intervals__params: find_covered_intervals__params
    abra__params: abra__params
    fix_mate_information__params: fix_mate_information__params
    base_recalibrator__params: base_recalibrator__params
    print_reads__params: print_reads__params

  out: [
    standard_bams,
    clipping_dirs,
    clipping_info,
    clstats1,
    clstats2,
    md_metrics,
    covint_list,
    covint_bed]

  ################################
  # Generate Collapsed Bams & QC #
  ################################

- id: standard_bam_to_collapsed_qc
  run: ./subworkflows/standard_bam_to_collapsed_qc.cwl
  in:
    tmp_dir: tmp_dir
    run_tools: run_tools
    marianas_collapsing__params: marianas_collapsing__params
    add_or_replace_read_groups__params: add_or_replace_read_groups__params
    waltz__params: waltz__params
    find_covered_intervals__params: find_covered_intervals__params
    abra__params: abra__params
    fix_mate_information__params: fix_mate_information__params

    standard_bams: standard_bam_generation/standard_bams

    patient_ids: patient_id
    fci__basq_fix: fci_2__basq_fix
    gene_list: gene_list
    reference_fasta: reference_fasta
    reference_fasta_fai: reference_fasta_fai

    add_rg_LB: add_rg_LB
    add_rg_ID: add_rg_ID
    add_rg_PU: add_rg_PU
    add_rg_SM: add_rg_SM
    add_rg_PL:
      valueFrom: $(inputs.add_or_replace_read_groups__params.add_rg_PL)
    add_rg_CN:
      valueFrom: $(inputs.add_or_replace_read_groups__params.add_rg_CN)

    project_name: project_name
    title_file: title_file
    A_on_target_positions: A_on_target_positions
    B_on_target_positions: B_on_target_positions
    noise__good_positions_A: noise__good_positions_A
    inputs_yaml: inputs_yaml
    pool_a_bed_file: pool_a_bed_file
    pool_b_bed_file: pool_b_bed_file
    gene_list: gene_list
    FP_config_file: FP_config_file

  out: [
    bam_dirs,
    combined_qc,
    qc_tables
  ]
