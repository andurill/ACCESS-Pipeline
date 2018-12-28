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
      - $import: ../../resources/run_params/schemas/mutect.yaml
      - $import: ../../resources/run_params/schemas/vardict.yaml

inputs:

  tmp_dir: Directory
  mutect_params: ../../resources/run_params/schemas/mutect.yaml#mutect_params
  vardict_params: ../../resources/run_params/schemas/vardict.yaml#vardict_params

  tumor_bam:
    type: File
    secondaryFiles: [^.bai]
  normal_bam:
    type: File
    secondaryFiles: [^.bai]
  tumor_sample_name: string
  normal_sample_name: string
  dbsnp:
    type: File
    secondaryFiles: [.idx]
  cosmic:
    type: File
    secondaryFiles: [.idx]
  bed_file: File
  refseq: File
  hotspot_vcf: File
  reference_fasta: File

outputs:

  mutect_vcf:
    type: File
    outputSource: mutect/output

  mutect_callstats:
    type: File
    outputSource: mutect/callstats_output

  vardict_vcf:
    type: File
    outputSource: vardict/output

steps:

  vardict:
    run: ../../cwl_tools/vardict/vardict_paired.cwl
    in:
      vardict_params: vardict_params
      reference_fasta: reference_fasta
      bed_file: bed_file
      tumor_bam: tumor_bam
      normal_bam: normal_bam
      tumor_sample_name: tumor_sample_name
      normal_sample_name: normal_sample_name

      column_for_region_end:
        valueFrom: $(inputs.vardict_params.column_for_region_end)
      column_for_region_start:
        valueFrom: $(inputs.vardict_params.column_for_region_start)
      column_for_chromosome:
        valueFrom: $(inputs.vardict_params.column_for_chromosome)
      column_for_gene_name:
        valueFrom: $(inputs.vardict_params.column_for_gene_name)
      allele_freq_thres:
        valueFrom: $(inputs.vardict_params.allele_freq_thres)
      min_num_variant_reads:
        valueFrom: $(inputs.vardict_params.min_num_variant_reads)
      output_file_name:
        valueFrom: $(inputs.tumor_sample_name + '.' + inputs.normal_sample_name + '.vardict.vcf')
    out: [output]

  mutect:
    run: ../../cwl_tools/mutect/mutect.cwl
    in:
      tmp_dir: tmp_dir
      mutect_params: mutect_params
      reference_sequence: reference_fasta
      dbsnp: dbsnp
      cosmic: cosmic
      intervals: bed_file
      input_file_normal: normal_bam
      input_file_tumor: tumor_bam
      tumor_sample_name: tumor_sample_name
      normal_sample_name: normal_sample_name

      read_filter:
        valueFrom: $(inputs.mutect_params.rf)
      downsample_to_coverage:
        valueFrom: $(inputs.mutect_params.dcov)
      fraction_contamination:
        valueFrom: $(inputs.mutect_params.fraction_contamination)
      minimum_mutation_cell_fraction:
        valueFrom: $(inputs.mutect_params.minimum_mutation_cell_fraction)
      vcf:
        valueFrom: $(inputs.tumor_sample_name + '.' + inputs.normal_sample_name + '.mutect.vcf')
      out:
        valueFrom: $(inputs.tumor_sample_name + '.' + inputs.normal_sample_name + '.mutect.txt')
    out: [output, callstats_output]
