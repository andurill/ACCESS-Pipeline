cwlVersion: v1.0

class: Workflow

requirements:
  SubworkflowFeatureRequirement: {}
  ScatterFeatureRequirement: {}
  InlineJavascriptRequirement: {}
  SchemaDefRequirement:
    types:
      - $import: ../resources/run_params/schemas/mutect.yaml
      - $import: ../resources/run_params/schemas/vardict.yaml
      - $import: ../resources/run_params/schemas/basic-filtering-vardict.yaml
      - $import: ../resources/run_params/schemas/basic-filtering-mutect.yaml
      - $import: ../resources/run_params/schemas/bcftools.yaml
      - $import: ../resources/run_params/schemas/vcf2maf.yaml
      - $import: ../resources/run_params/schemas/gbcms_params.yaml
      - $import: ../resources/run_params/schemas/delly.yaml

inputs:

  tmp_dir: Directory
  project_name: string
  version: string

  mutect_params: ../resources/run_params/schemas/mutect.yaml#mutect_params
  vardict_params: ../resources/run_params/schemas/vardict.yaml#vardict_params
  basicfiltering_vardict_params: ../resources/run_params/schemas/basic-filtering-vardict.yaml#basicfiltering_vardict_params
  basicfiltering_mutect_params: ../resources/run_params/schemas/basic-filtering-mutect.yaml#basicfiltering_mutect_params
  bcftools_params: ../resources/run_params/schemas/bcftools.yaml#bcftools_params
  vcf2maf_params: ../resources/run_params/schemas/vcf2maf.yaml#vcf2maf_params
  gbcms_params: ../resources/run_params/schemas/gbcms_params.yaml#gbcms_params
  delly_params: ../resources/run_params/schemas/delly.yaml#delly_params

  hotspots: File

  #########################################
  # Tumor bams should be sorted in paired #
  # order with Normal bams                #
  #########################################
  tumor_bams:
    type: File[]
    secondaryFiles: [^.bai]
  normal_bams:
    type: File[]
    secondaryFiles: [^.bai]
  genotyping_bams:
    type: File[]
    secondaryFiles: [^.bai]

  tumor_sample_names: string[]
  normal_sample_names: string[]
  genotyping_bams_ids: string[]

  bed_file: File
  refseq: File
  hotspot_vcf: File
  hotspot_list: File

  dbsnp:
    type: File
    secondaryFiles: [.idx]
  cosmic:
    type: File
    secondaryFiles: [.idx]
  ref_fasta:
    type: File
    secondaryFiles: [.fai, ^.dict]

############### Todo: section not finished:
#  hapmap:
#    type: File
#    secondaryFiles:
#      - .idx
#  indels_1000g:
#    type: File
#    secondaryFiles:
#      - .idx
#  snps_1000g:
#    type: File
#    secondaryFiles:
#      - .idx
  exac_filter:
    type: File
    secondaryFiles:
      - .tbi
#  conpair_markers: File
#  conpair_markers_bed: File
#################

outputs:

  concatenated_vcf:
    type: File[]
    outputSource: module_3/concatenated_vcf

  mutect_vcf:
    type: File[]
    outputSource: module_3/mutect_vcf

  mutect_callstats:
    type: File[]
    outputSource: module_3/mutect_callstats

  vardict_vcf:
    type: File[]
    outputSource: module_3/vardict_vcf

  mutect_normalized_vcf:
    type: File[]
    outputSource: module_3/mutect_normalized_vcf

  vardict_normalized_vcf:
    type: File[]
    outputSource: module_3/vardict_normalized_vcf

  final_maf:
    type: File[]
    outputSource: module_4/maf

  hotspots_filtered_maf:
    type: File[]
    outputSource: module_4/hotspots_filtered_maf

  consolidated_maf:
    type: File[]
    outputSource: module_4/consolidated_maf

  fillout_maf:
    type: File[]
    outputSource: module_4/fillout_maf

  delly_sv:
    type:
      type: array
      items:
        type: array
        items: File
    outputSource: structural_variants/delly_sv

  delly_filtered_sv:
    type:
      type: array
      items:
        type: array
        items: File
    outputSource: structural_variants/delly_filtered_sv

  merged_structural_variants:
    type: File[]
    outputSource: structural_variants/merged_structural_variants

  merged_structural_variants_unfiltered:
    type: File[]
    outputSource: structural_variants/merged_structural_variants_unfiltered

  structural_variants_maf:
    type: File[]
    outputSource: structural_variants/structural_variants_maf


steps:

  ###################
  # Variant Calling #
  ###################

  module_3:
    run: ./module-3.cwl
    in:
      tmp_dir: tmp_dir
      tumor_bams: tumor_bams
      normal_bams: normal_bams
      tumor_sample_names: tumor_sample_names
      normal_sample_names: normal_sample_names
      bed_file: bed_file
      refseq: refseq
      hotspot_vcf: hotspot_vcf
      ref_fasta: ref_fasta
      dbsnp: dbsnp
      cosmic: cosmic
      mutect_params: mutect_params
      vardict_params: vardict_params
      basicfiltering_vardict_params: basicfiltering_vardict_params
      basicfiltering_mutect_params: basicfiltering_mutect_params
      bcftools_params: bcftools_params
    out: [
      concatenated_vcf,
      mutect_vcf,
      mutect_callstats,
      vardict_vcf,
      mutect_normalized_vcf,
      vardict_normalized_vcf]

  ##############
  # Genotyping #
  ##############

  module_4:
    run: ./module-4.cwl
    in:
      vcf2maf_params: vcf2maf_params
      tmp_dir: tmp_dir
      hotspots: hotspots
      gbcms_params: gbcms_params
      combine_vcf: module_3/concatenated_vcf
      genotyping_bams: genotyping_bams
      genotyping_bams_ids: genotyping_bams_ids
      tumor_sample_name: tumor_sample_names
      normal_sample_name: normal_sample_names
      ref_fasta: ref_fasta
      exac_filter: exac_filter
      hotspot_list: hotspot_list
    out: [maf, hotspots_filtered_maf, consolidated_maf, fillout_maf]
    scatter: [combine_vcf, tumor_sample_name, normal_sample_name]
    scatterMethod: dotproduct

  #######################
  # Structural Variants #
  #######################

  structural_variants:
    run: ./module-6.cwl
    in:
      tmp_dir: tmp_dir
      delly_params: delly_params
      vcf2maf_params: vcf2maf_params
      tumor_bam: tumor_bams
      normal_bam: normal_bams
      normal_sample_name: tumor_sample_names
      tumor_sample_name: normal_sample_names
      reference_fasta: ref_fasta
      exac_filter: exac_filter
      delly_type:
        valueFrom: $(['DEL', 'DUP', 'BND', 'INV', 'INS'])

      vep_data:
        valueFrom: $(inputs.vcf2maf_params.vep_data)
    out: [
      delly_sv,
      delly_filtered_sv,
      merged_structural_variants,
      merged_structural_variants_unfiltered,
      structural_variants_maf]
    scatter: [tumor_bam, normal_bam, tumor_sample_name, normal_sample_name]
    scatterMethod: dotproduct
