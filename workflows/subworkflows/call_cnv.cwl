cwlVersion: v1.0

class: Workflow

requirements:
  MultipleInputFeatureRequirement: {}
  ScatterFeatureRequirement: {}
  SubworkflowFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  StepInputExpressionRequirement: {}

inputs:

  file_path: string
  coverage_script: string
  copy_number_script: string
  loess_normalize_script: string

  tumor_sample_list: File
  normal_sample_list: File
  targets_coverage_bed: File
  targets_coverage_annotation: File
  reference_fasta: File

  project_name_cnv: string
  threads: int

outputs:
#check this with example output JIRA
    tumors_covg:
        type: File
        outputSource: coverage/tumors_covg
    normals_covg:
        type: File
        outputSource: coverage/normals_covg
    bam_list:
        type: File[]
        outputSource: coverage/bam_list
    coverage_std_out:
      type: File
      outputSource: coverage/standard_out
    coverage_std_err:
      type: File
      outputSource: coverage/standard_err

    tumor_loess_text:
        type: File
        outputSource: loess_tumor/loess_text
    normal_loess_text:
        type: File
        outputSource: loess_normal/loess_text
    tumor_loess_pdf:
        type: File
        outputSource: loess_tumor/loess_pdf
    normal_loess_pdf:
        type: File
        outputSource: loess_normal/loess_pdf
    loess_tumor_std_out:
      type: File
      outputSource: loess_tumor/standard_out
    loess_tumor_std_err:
      type: File
      outputSource: loess_tumor/standard_err
    loess_normal_std_out:
      type: File
      outputSource: loess_normal/standard_out
    loess_normal_std_err:
      type: File
      outputSource: loess_normal/standard_err

    genes_file:
        type: File
        outputSource: copy_number/genes_file
    probes_file:
        type: File
        outputSource: copy_number/probes_file
    intragenic_file:
        type: File
        outputSource: copy_number/intragenic_file
    copy_pdf:
        type: File
        outputSource: copy_number/copy_pdf
    seg_files:
        type: File[]
        outputSource: copy_number/seg_files
    copy_standard_out:
        type: File
        outputSource: copy_number/copy_standard_out
    copy_standard_err:
        type: File
        outputSource: copy_number/copy_standard_err

steps:

  coverage:
    run: ../../cwl_tools/cnv/coverage.cwl
    in:
      coverage_script: coverage_script
      project_name_cnv: project_name_cnv
      file_path: file_path
      threads: threads
      tumor_sample_list: tumor_sample_list
      normal_sample_list: normal_sample_list
      targets_coverage_bed: targets_coverage_bed
      reference_fasta: reference_fasta

    out: [tumors_covg, normals_covg, bam_list, standard_out, standard_err]


  loess_tumor:
    run: ../../cwl_tools/cnv/loess.cwl
    in:
      loess_normalize_script: loess_normalize_script
      project_name_cnv: project_name_cnv
      file_path: file_path
      coverage_file: coverage/tumors_covg
      run_type:
        default: tumor
      targets_coverage_annotation: targets_coverage_annotation

    out: [loess_text, loess_pdf, standard_out, standard_err]


  loess_normal:
    run: ../../cwl_tools/cnv/loess.cwl
    in:
      loess_normalize_script: loess_normalize_script
      project_name_cnv: project_name_cnv
      file_path: file_path
      coverage_file: coverage/normals_covg
      run_type:
        default: normal
      targets_coverage_annotation: targets_coverage_annotation

    out: [loess_text, loess_pdf, standard_out, standard_err]


  copy_number:
    run: ../../cwl_tools/cnv/copynumber.cwl
    in:
      copy_number_script: copy_number_script
      project_name_cnv: project_name_cnv
      file_path: file_path
      loess_normals: loess_normal/loess_text
      loess_tumors: loess_tumor/loess_text
      do_full:
        default: MIN
      targets_coverage_annotation: targets_coverage_annotation

    out: [genes_file, probes_file, copy_pdf, intragenic_file, seg_files, copy_standard_out, copy_standard_err]