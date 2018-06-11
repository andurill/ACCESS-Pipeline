#!/usr/bin/env cwl-runner

cwlVersion: v1.0

class: CommandLineTool

baseCommand: [make_umi_qc_tables.sh]

requirements:
- class: InlineJavascriptRequirement

inputs:

  A_on_target_positions:
    type: File
    inputBinding:
      position: 1

  B_on_target_positions:
    type: File
    inputBinding:
      position: 2

  folders:
    type: Directory[]
    inputBinding:
      position: 3

outputs:

  family_sizes:
    type: File
    outputBinding:
      glob: 'family-sizes.txt'

  family_types_A:
    type: File
    outputBinding:
      glob: 'family-types-A.txt'

  family_types_B:
    type: File
    outputBinding:
      glob: 'family-types-B.txt'