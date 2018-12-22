cwlVersion: v1.0

class: Workflow

requirements:
    MultipleInputFeatureRequirement: {}
    ScatterFeatureRequirement: {}
    SubworkflowFeatureRequirement: {}
    InlineJavascriptRequirement: {}
    StepInputExpressionRequirement: {}

inputs:
  input_maf: File

outputs:
  portal_file:
    type: File
    outputSource: portal_format_output/portal_formatted

steps:
  formatting_remove_comments:
    in:
      input_maf: input_maf
      output_filename:
        valueFrom: $(inputs.input_maf.basename.replace('.maf', '.grepped.txt'))
    out: [comment_removed]

    run:
      class: CommandLineTool
      baseCommand: ['grep', '^[^#;]']
      stdout: $(inputs.output_filename)
      inputs:
        input_maf:
          type: File
          inputBinding:
            position: 1
        output_filename: string
      outputs:
        comment_removed:
          type: stdout

  extract_columns:
    in:
      grepped_file: formatting_remove_comments/comment_removed
      output_filename:
         valueFrom: $(inputs.grepped_file.basename.replace('.grepped.txt', '.extracted.txt'))
    out: [extracted_file]

    run:
      class: CommandLineTool
      baseCommand: []
      arguments:
        - awk
        - -F
        - "\t"
        - 'NR==1 { for(i=1;i<=NF;i++){ f[$i]=i } } { print \$(f["Hugo_Symbol"])"\\t"\$(f["Entrez_Gene_Id"])"\\t"\$(f["Center"])"\\t"\$(f["Tumor_Sample_Barcode"])"\\t"\$(f["Fusion"])"\\t"\$(f["Method"])"\\t"\$(f["Frame"])}'
      stdout: $(inputs.output_filename)

      inputs:
        grepped_file:
          type: File
          inputBinding:
            position: 1
        output_filename: string
      outputs:
        extracted_file:
          type: stdout

  add_two_columns: # RNA_support and no, DNA_support and yes
    in:
      extracted_file: extract_columns/extracted_file
      output_filename:
         valueFrom: $(inputs.extracted_file.basename.replace('.extracted.txt', '.columns_added.txt'))
    out: [columns_added]

    run:
      class: CommandLineTool
      baseCommand: [sed, 1s/$/\\tDNA_support\\tRNA_support/;2,$s/$/\\tyes\\tno/]
      stdout: $(inputs.output_filename)
      inputs:
        extracted_file:
          type: File
          inputBinding:
            position: 1
        output_filename: string
      outputs:
        columns_added:
          type: stdout

  portal_format_output:
    in:
      sed_file: add_two_columns/columns_added
      output_filename:
        valueFrom: $(inputs.sed_file.basename.replace('.columns_added.txt', '.portal.txt'))
    out: [portal_formatted]

    run:
      class: CommandLineTool
      baseCommand: []
      arguments:
        - awk
        - -F
        - "\t"
        - 'NR==1 { for(i=1;i<=NF;i++){ f[$i]=i } } { print \$(f["Hugo_Symbol"])"\\t"\$(f["Entrez_Gene_Id"])"\\t"\$(f["Center"])"\\t"\$(f["Tumor_Sample_Barcode"])"\\t"\$(f["Fusion"])"\\t"\$(f["DNA_support"])"\\t"\$(f["RNA_support"])"\\t"\$(f["Method"])"\\t"\$(f["Frame"])}'
      stdout: $(inputs.output_filename)
      inputs:
        sed_file:
          type: File
          inputBinding:
            position: 1
        output_filename: string
      outputs:
        portal_formatted: stdout
