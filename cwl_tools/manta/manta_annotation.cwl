cwlVersion: v1.0

class: CommandLineTool

requirements:
  ResourceRequirement:
    ramMin: 16000

arguments:
- $(inputs.sv_repo.path + '/scripts/iAnnotateSV.sh')

inputs:

  sv_repo: Directory

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
  
  java:
    type: string
    inputBinding:
      position: 7

outputs:

  sv_file_annotated:
    type: File
    outputBinding:
      glob: $(inputs.sample_id + '_Annotated_Evidence-annotated.txt')