#!/usr/bin/env cwl-runner

cwlVersion: v1.0

class: CommandLineTool

arguments:
- $(inputs.java)
- -Xmx60g
- -Djava.io.tmpdir=/scratch
- -jar
- $(inputs.abra)

requirements:
  InlineJavascriptRequirement: {}
  ResourceRequirement:
    ramMin: 62000
    coresMin: 8

doc: |
  None

inputs:
  java: string
  abra: string

  input_bams:
    type:
      type: array
      items: File
    inputBinding:
      prefix: --in
      itemSeparator: ','
    secondaryFiles:
    - ^.bai

  scratch_dir:
    type: string
  patient_id:
    type: string

  working_directory:
    type: string
    inputBinding:
      prefix: --working

  reference_fasta:
    type: string
    inputBinding:
      prefix: --ref

  targets:
    type: File
    inputBinding:
      prefix: --targets

  threads:
    type: int
    inputBinding:
      prefix: --threads

  kmer:
    type: string
    inputBinding:
      prefix: --kmer

  mad:
    type: int
    inputBinding:
      prefix: --mad

  out:
    type:
      type: array
      items: string
    inputBinding:
      itemSeparator: ','
      prefix: --out

outputs:

  bams:
    type: File[]
    outputBinding:
      # Todo: Only specify in one place.
      glob: '*_IR.bam'