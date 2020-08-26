cwlVersion: v1.0

class: CommandLineTool

requirements:
  ResourceRequirement:
    ramMin: 16000

arguments:
- $(inputs.sv_repo + '/scripts/iAnnotateSV.sh')

inputs:
  sv_repo:
    type: string

  vcf:
    type: File
    inputBinding:
      position: 1

  sample_id:
    type: string
    inputBinding:
      position: 2

  output_dir:
    type: string
    inputBinding:
      position: 3

  manta:
    type: Directory
    inputBinding:
      position: 4

  reference_fasta:
    type: File
    inputBinding:
      position: 5

  manta_python:
    type: string
    inputBinding:
      position: 6

outputs:
  manta_somatic_vcf:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_somaticSV.vcf')

  manta_somatic_inv_corrected_vcf:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_somaticSV_inv_corrected.vcf')

  manta_somatic_inv_corrected_edited_vcf:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_somaticSV_inv_corrected_edited.vcf')

  manta_somatic_inv_corrected_edited_tab:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_somaticSV_inv_corrected_edited.tab')

  sv_file_annotated:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_Annotated.txt')

  sv_file_annotated_ev:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_Annotated_Evidence.txt')
