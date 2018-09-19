import sys
import argparse
import ruamel.yaml
import numpy as np
import pandas as pd

# constants include the paths to the config files
from ..constants import *
from ..util import reverse_complement


##################################
# Pipeline Kickoff Step #2
#
# Usage Example:
#
# create_inputs_from_title_file \
#   -i ./XX_title_file.txt \
#   -d ./Innovation-Pipeline/test/test_data/new_test_data
#
# This module is used to create a yaml file that will be supplied to the pipeline run.
#
# This yaml file will include three main types of ingredient:
#
#   1. Paths to fastq files and sample sheets
#   2. Paths to resources required during the run (e.g. reference fasta, bed files etc.)
#   3. Values for parameters for the individual tools (e.g. min coverage values, mapq thresholds etc.)
#
# The requirements for running this module include:
#
#   1. Read 1 fastq, Read 2 fastq, and SampleSheet.csv are found in the same directory
#   2. The Sample ID from the title_file matches with at least some part of the path in the fastq files and sample sheet
#   3. The Patient ID from the title_file is found in at least one of the fastq files
#
# Todo: This file is too large


# Template identifier string that will get replaced with the project root location
PIPELINE_ROOT_PLACEHOLDER = '$PIPELINE_ROOT'

# Strings to target when looking for Illumina run files
FASTQ_1_FILE_SEARCH = '_R1_001.fastq.gz'
FASTQ_2_FILE_SEARCH = '_R2_001.fastq.gz'
SAMPLE_SHEET_FILE_SEARCH = 'SampleSheet.csv'

ADAPTER_1 = 'GATCGGAAGAGC'
ADAPTER_2 = 'AGATCGGAAGAGC'

# Delimiter for printing logs
DELIMITER = '\n' + '*' * 20 + '\n'
# Delimiter for inputs file sections
INPUTS_FILE_DELIMITER = '\n\n' + '# ' + '--' * 30 + '\n\n'


def load_fastqs(data_dir):
    """
    Recursively find files in `data_dir` with the given `file_regex`

    Todo: need to support multiple R1 / R2 fastqs per patient?
    Or maybe not b/c "The last segment is always 001":
    https://support.illumina.com/content/dam/illumina-support/documents/documentation/software_documentation/bcl2fastq/bcl2fastq2_guide_15051736_v2.pdf
    Page 19

    Note:
    os.walk yields a 3-list (dirpath, dirnames, filenames)
    """
    # Gather Sample Sub-directories (but leave out the parent dir)
    folders = list(os.walk(data_dir, followlinks=True))

    # Filter to those that contain a read 1, read 2, and sample sheet
    folders_2 = filter(lambda folder: any([FASTQ_1_FILE_SEARCH in x for x in folder[2]]), folders)
    folders_3 = filter(lambda folder: any([FASTQ_2_FILE_SEARCH in x for x in folder[2]]), folders_2)
    folders_4 = filter(lambda folder: any([SAMPLE_SHEET_FILE_SEARCH in x for x in folder[2]]), folders_3)

    # Issue a warning if not all folders had necessary files (-1 to exclude topmost directory)
    if not len(folders) - 1 == len(folders_4):
        print(DELIMITER + 'Warning, some samples may not have a Read 1, Read 2, or sample sheet. '
                          'Please manually check inputs.yaml')

        print('All sample folders: ' + str(folders))
        print('Sample folders with correct result files: ' + str(folders_4))

    # Take just the files
    files_flattened = [os.path.join(dirpath, f) for (dirpath, dirnames, filenames) in folders_4 for f in filenames]

    # Separate into three lists
    fastq1 = filter(lambda x: FASTQ_1_FILE_SEARCH in x, files_flattened)
    fastq1 = [{'class': 'File', 'path': path} for path in fastq1]
    fastq2 = filter(lambda x: FASTQ_2_FILE_SEARCH in x, files_flattened)
    fastq2 = [{'class': 'File', 'path': path} for path in fastq2]
    sample_sheet = filter(lambda x: SAMPLE_SHEET_FILE_SEARCH in x, files_flattened)
    sample_sheet = [{'class': 'File', 'path': path} for path in sample_sheet]

    return fastq1, fastq2, sample_sheet


def perform_duplicate_barcodes_check(title_file):
    """
    Check that no two samples have the same barcode 1 or barcode 2

    Note that this only works when performing this check on an individual lane,
    as barcodes may be reused across lanes.
    """
    if np.sum(title_file[TITLE_FILE__BARCODE_INDEX_1_COLUMN].duplicated()) > 0:
        raise Exception(DELIMITER + 'Duplicate barcodes for barcode 1. Exiting.')

    if np.sum(title_file[TITLE_FILE__BARCODE_INDEX_2_COLUMN].duplicated()) > 0:
        raise Exception(DELIMITER + 'Duplicate barcodes for barcode 2, lane.')


def get_pos(title_file, fastq_object):
    """
    Return position of `fastq_object` in 'Sample_ID' column of title_file

    Used for sorting the entries in the inputs file so that Scatter steps will pair the correct files

    :param: title_file pandas.DataFrame with all required title_file columns (see constants.py)
    :param: fastq_object dict with `class`: `File` and `path`: `path_to_fastq` as read in by ruamel.round_trip_load()
    :raises: Exception if more than one sample ID in the `title_file` matches this fastq file, or if no sample ID's
            in the `title_file` match this fastq file
    """
    def contained_in(sample_id, fastq):
        """
        Helper method to sort list of fastqs.
        Returns 1 if `sample_id` contained in `fastq`'s path, 0 otherwise
        """
        found = sample_id in fastq['path']

        if found:
            return 1
        else:
            return 0

    boolv = title_file[TITLE_FILE__SAMPLE_ID_COLUMN].apply(contained_in, fastq=fastq_object)

    if np.sum(boolv) > 1:
        raise Exception('More than one fastq found for patient, exiting.')

    # If there are no matches, throw error
    if np.sum(boolv) < 1:
        err_string = DELIMITER + 'Error, matching sample ID for file {} not found in title file'
        print >> sys.stderr, err_string.format(fastq_object)
        raise Exception('Please double check the order of the fastqs in the final inputs.yaml file')

    pos = np.argmax(boolv)
    return pos


def sort_fastqs(fastq1, fastq2, sample_sheet, title_file):
    """
    Helper method to sort fastq paths based on title_file ordering.
    Lists of inputs in our yaml file need to be ordered the same order as each other.
    An alternate method might involve using Record types as a cleaner solution.
    """
    fastq1 = sorted(fastq1, key=lambda f: get_pos(title_file, f))
    fastq2 = sorted(fastq2, key=lambda f: get_pos(title_file, f))
    sample_sheet = sorted(sample_sheet, key=lambda s: get_pos(title_file, s))
    return fastq1, fastq2, sample_sheet


def remove_missing_samples_from_title_file(title_file, fastq1, title_file_path):
    """
    If samples IDs from title file aren't found in data directory,
    issue a warning and remove them from the title file

    # Todo: Should we instead raise an error and not continue?
    """
    found_boolv = np.array([any([sample in f['path'] for f in fastq1]) for sample in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]])
    samples_not_found = title_file.loc[~found_boolv, TITLE_FILE__SAMPLE_ID_COLUMN]

    if samples_not_found.shape[0] > 0:
        print(DELIMITER + 'Error: The following samples were missing either a read 1 fastq, read 2 fastq, or sample sheet. ' +
                          'These samples will be removed from the title file so that the remaining samples can be run.')
        print('Please perform a manual check on the inputs file before running the pipeline.')
        print(samples_not_found)

    title_file = title_file.loc[found_boolv, :]
    title_file.to_csv(title_file_path, sep='\t', index=False)
    return title_file


def remove_missing_fastq_samples(fastq1, fastq2, sample_sheet, title_file):
    """
    If a sample ID from the title file is not found in any of the paths to the fastqs, remove it from the title file.

    Todo: For the SampleSheet files, this relies on the parent folder containing the sample name
    """
    fastq1 = filter(lambda f: any([sid in f['path'] for sid in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]]), fastq1)
    fastq2 = filter(lambda f: any([sid in f['path'] for sid in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]]), fastq2)
    sample_sheet = filter(lambda s: any([sid in s['path'] for sid in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]]), sample_sheet)

    return fastq1, fastq2, sample_sheet


def check_i5_index(title_file_i5, sample_sheet_i5):
    """
    The i5 index (or "Index2" in the SampleSheet.csv file) will either match as is, or as a reverse-complement,
    based on the machine the sequencing was done on.

    :param title_file_i5:
    :param sample_sheet_i5:
    :return:
    """
    rev_comp_i5_barcode = reverse_complement(sample_sheet_i5)

    i5_matches_non_reverse_complemented = sample_sheet_i5 == title_file_i5
    i5_matches_reverse_complemented = rev_comp_i5_barcode == title_file_i5

    err_string = 'i5 index from title file {} does not match i5 index from SampleSheet {}. Aborting.' \
        .format(title_file_i5, sample_sheet_i5)

    assert i5_matches_non_reverse_complemented or i5_matches_reverse_complemented, err_string

    if i5_matches_non_reverse_complemented:
        return NON_REVERSE_COMPLEMENTED
    elif i5_matches_reverse_complemented:
        return REVERSE_COMPLEMENTED


def perform_barcode_index_checks_i5(title_file, sample_sheets):
    """
    The i5 index (or "Index2" in the SampleSheet.csv file) will either match as is, or as a reverse-complement,
    based on the machine the sequencing was done on.

    :param title_file:
    :param sample_sheets:
    :return:
    """
    i5_sequencer_types = []
    for sample_id in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]:
        cur_sample = title_file[title_file[TITLE_FILE__SAMPLE_ID_COLUMN] == sample_id]
        title_file_i5 = cur_sample[TITLE_FILE__BARCODE_INDEX_2_COLUMN].values[0]

        matching_sample_sheets = [s for s in sample_sheets if sample_id in s.get('path')]
        assert len(matching_sample_sheets) == 1
        sample_sheet = matching_sample_sheets[0]
        sample_sheet_df = pd.read_csv(sample_sheet['path'], sep=',')

        try:
            sample_sheet_i5 = sample_sheet_df['Index2'].values[0]
        except KeyError:
            print('Index2 not found in SampleSheet.csv. Skipping i5 barcode index validation.')
            return

        i5_sequencer_types.append(check_i5_index(title_file_i5, sample_sheet_i5))

    all_non_reverse_complemented = all([match_type == NON_REVERSE_COMPLEMENTED for match_type in i5_sequencer_types])
    all_reverse_complemented = all([match_type == REVERSE_COMPLEMENTED for match_type in i5_sequencer_types])

    assert all_non_reverse_complemented or all_reverse_complemented, 'Not all barcodes followed same i5 index scheme'

    if all_non_reverse_complemented:
        print(DELIMITER + 'All i5 barcodes match without reverse-complementing, sequencer was one of the following:')
        print('NovaSeq\nMiSeq\nHiSeq2500')

    elif all_reverse_complemented:
        print(DELIMITER + 'All i5 barcodes match after reverse-complementing, sequencer was one of the following:')
        print('HiSeq4000\nMiniSeq\nNextSeq')


def perform_barcode_index_checks(title_file, sample_sheets):
    """
    Confirm that the barcode indexes in the title file,
    match to what is listed in the Sample Sheet files from the Illumina Run

    :param title_file:
    :param sample_sheets:
    :return:
    """
    # i7 (Index1) checks
    for sample_id in title_file[TITLE_FILE__SAMPLE_ID_COLUMN]:
        cur_sample = title_file[title_file[TITLE_FILE__SAMPLE_ID_COLUMN] == sample_id]
        title_file_i7 = cur_sample[TITLE_FILE__BARCODE_INDEX_1_COLUMN].values[0]

        matching_sample_sheets = [s for s in sample_sheets if sample_id in s.get('path')]

        assert len(matching_sample_sheets) == 1
        sample_sheet = matching_sample_sheets[0]
        sample_sheet_df = pd.read_csv(sample_sheet['path'], sep=',')

        # i7 Sequence should always match
        sample_sheet_i7 = sample_sheet_df['Index'].values[0]

        err_template = 'i7 index does not match for sample {}. Aborting. {} != {}'
        err_string = err_template.format(sample_id, sample_sheet_i7, title_file_i7)
        assert sample_sheet_i7 == title_file_i7, err_string

    # i5 index check is somewhat more involved
    perform_barcode_index_checks_i5(title_file, sample_sheets)


def include_fastqs_params(fh, data_dir, title_file, title_file_path, force):
    """
    Write fastq1, fastq2, read group identifiers and sample_sheet file references to yaml inputs file.

    :param fh:
    :param data_dir:
    :param title_file:
    :param title_file_path:
    :param force:
    """
    # Load and sort our data files
    fastq1, fastq2, sample_sheets = load_fastqs(data_dir)
    # Get rid of data files that don't have an entry in the title_file
    fastq1, fastq2, sample_sheets = remove_missing_fastq_samples(fastq1, fastq2, sample_sheets, title_file)
    # Get rid of entries from title file that are missing data files
    title_file = remove_missing_samples_from_title_file(title_file, fastq1, title_file_path)
    # Sort everything based on the ordering in the title_file
    fastq1, fastq2, sample_sheets = sort_fastqs(fastq1, fastq2, sample_sheets, title_file)

    if not force:
        # Check that we have the same number of everything
        perform_length_checks(fastq1, fastq2, sample_sheets, title_file)
        # Check that patient ids are found in fastq filenames
        # Check the barcode sequences in the title_file against the sequences in the sample_sheets
        perform_barcode_index_checks(title_file, sample_sheets)

    samples_info = {
        'fastq1': fastq1,
        'fastq2': fastq2,
        'sample_sheet': sample_sheets,
        'adapter': [ADAPTER_1] * len(fastq1),
        'adapter2': [ADAPTER_2] * len(fastq2),

        # Todo: what's the difference between ID & SM?
        # Todo: do we want the whole filename for ID? (see BWA IMPACT logs)
        # or abbreviate it (might be the way they do it in Roslin)
        'add_rg_ID': title_file[TITLE_FILE__SAMPLE_ID_COLUMN].tolist(),
        'add_rg_SM': title_file[TITLE_FILE__SAMPLE_ID_COLUMN].tolist(),
        'add_rg_LB': title_file[TITLE_FILE__LANE_COLUMN].tolist(),

        # Todo: should we use one or two barcodes in the PU field if they are different?
        'add_rg_PU': title_file[TITLE_FILE__BARCODE_ID_COLUMN].tolist(),

        # Patient ID needs to be a string, in case it is currently an integer
        'patient_id': [str(p) for p in title_file[TITLE_FILE__PATIENT_ID_COLUMN].tolist()]
    }

    # Trim whitespace
    for key in samples_info:
        samples_info[key] = [x.strip() if type(x) == str else x for x in samples_info[key]]

    fh.write(ruamel.yaml.dump(samples_info))


def substitute_project_root(yaml_file):
    """
    Substitute in the ROOT_PATH variable based on our current installation directory

    The purpose of this method is to support referencing resources in the resources folder

    :param: yaml_file A yaml file read in by ruamel's round_trip_load() method
    """
    for key in yaml_file.keys():
        # If we are dealing with a File object
        if 'path' in yaml_file[key]:
            new_value = yaml_file[key]['path'].replace(PIPELINE_ROOT_PLACEHOLDER, ROOT_DIR)
            yaml_file[key]['path'] = new_value

        # If we are dealing with a string
        # Todo: these should be replaced with File types
        if type(yaml_file[key]) == str:
            new_value = yaml_file[key].replace(PIPELINE_ROOT_PLACEHOLDER, ROOT_DIR)
            yaml_file[key] = new_value

    return yaml_file


def include_file_resources(fh, file_resources_path):
    """
    Write the paths to the resource files that the pipeline needs into the inputs yaml file.

    :param: fh File Handle to the inputs file for the pipeline
    :param: file_resources_path String representing full path to our resources file
    """
    with open(file_resources_path, 'r') as stream:
        file_resources = ruamel.yaml.round_trip_load(stream)

    file_resources = substitute_project_root(file_resources)
    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(file_resources))


def include_run_params(fh, run_params_path):
    """
    Load and write our default run parameters to the pipeline inputs file

    :param fh: File Handle to the pipeline inputs yaml file
    :param run_params_path:  String representing full path to the file with our default tool parameters for this run
    """
    with open(run_params_path, 'r') as stream:
        other_params = ruamel.yaml.round_trip_load(stream)

    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(other_params))


def include_resource_overrides(fh):
    """
    Load and write our ResourceRequirement overrides for testing

    :param fh: File handle for pipeline yaml inputs
    """
    with open(RESOURCE_OVERRIDES_FILE_PATH, 'r') as stream:
        resource_overrides = ruamel.yaml.round_trip_load(stream)

    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(resource_overrides))


def include_tool_resources(fh, tool_resources_file_path):
    """
    Load and write our ResourceRequirement overrides for testing

    :param fh: File handle for pipeline yaml inputs
    :param tool_resources_file_path: path to file that contains paths to tools
    """
    with open(tool_resources_file_path, 'r') as stream:
        tool_resources = ruamel.yaml.round_trip_load(stream)
        tool_resources = substitute_project_root(tool_resources)

    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(tool_resources))


def perform_length_checks(fastq1, fastq2, sample_sheet, title_file):
    """
    Check whether the title file matches input fastqs

    Todo: we might want an option to remove fastqs or rows from the title_file instead of throwing error,
    in the event that we use this script on a subset of the fastqs in a pool

    :param fastq1: List[dict] where each dict is a ruamel file object with `class` and `path` keys,
            (`path` being the path to the read 1 fastq)
    :param fastq2: List[dict] where each dict is a ruamel file object with `class` and `path` keys,
            (`path` being the path to the read 2 fastq)
    :param sample_sheet: List[dict] where each dict is a ruamel file object with `class` and `path` keys,
            (`path` being the path to the sample sheet)
    :param title_file:
    """
    try:
        assert len(fastq1) == len(fastq2)
    except AssertionError as e:
        print(DELIMITER + 'Error: Different number of read 1 and read 2 fastqs: {}'.format(repr(e)))
        print('fastq1: {}'.format(len(fastq1)))
        print('fastq2: {}'.format(len(fastq2)))
    try:
        assert len(sample_sheet) == len(fastq1)
    except AssertionError as e:
        print(DELIMITER + 'Error: Different number of sample sheet files & read 1 fastqs: {}'.format(repr(e)))
        print('fastq1: {}'.format(len(fastq1)))
        print('sample_sheets: {}'.format(len(sample_sheet)))
    try:
        assert title_file.shape[0] == len(fastq1)
    except AssertionError as e:
        print(DELIMITER + 'Error: Different number of fastqs files and samples in title file: {}'.format(repr(e)))
        print('fastq1: {}'.format(len(fastq1)))
        print('title file length: {}'.format(title_file.shape[0]))


def include_collapsing_params(fh, test=False, local=False):
    """
    Load and write our Collapsing & QC parameters

    :param fh: File handle for pipeline yaml inputs
    :param test: Whether to include test or production collapsing params
    :param local:
    """
    if local:
        # Local run params are same as Test params
        collapsing_parameters = RUN_PARAMS_TEST_COLLAPSING
        collapsing_files = RUN_FILES_LOCAL_COLLAPSING
    elif test:
        collapsing_parameters = RUN_PARAMS_TEST_COLLAPSING
        collapsing_files = RUN_FILES_TEST_COLLAPSING
    else:
        collapsing_parameters = RUN_PARAMS_COLLAPSING
        collapsing_files = RUN_FILES_COLLAPSING

    with open(collapsing_parameters, 'r') as stream:
        collapsing_parameters = ruamel.yaml.round_trip_load(stream)

    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(collapsing_parameters))

    with open(collapsing_files, 'r') as stream:
        file_resources = ruamel.yaml.round_trip_load(stream)

    file_resources = substitute_project_root(file_resources)

    fh.write(INPUTS_FILE_DELIMITER + ruamel.yaml.round_trip_dump(file_resources))


def write_inputs_file(args, title_file, output_file_name):
    """
    Main function to write our inputs.yaml file.
    Contains most of the logic related to which inputs to use based on the type of run

    :param args:
    :param title_file:
    :param output_file_name:
    """
    tool_resources_file_path = TOOL_RESOURCES_LUNA

    if args.local:
        # Local run params are same as Test params
        run_params_path = RUN_PARAMS_TEST
        run_files_path = RUN_FILES_LOCAL
        tool_resources_file_path = TOOL_RESOURCES_LOCAL
    elif args.test:
        run_params_path = RUN_PARAMS_TEST
        run_files_path = RUN_FILES_TEST
    else:
        run_params_path = RUN_PARAMS
        run_files_path = RUN_FILES

    # Actually start writing the inputs file
    fh = open(output_file_name, 'wb')

    include_fastqs_params(fh, args.data_dir, title_file, args.title_file_path, args.force)
    include_run_params(fh, run_params_path)
    include_file_resources(fh, run_files_path)
    include_tool_resources(fh, tool_resources_file_path)

    if args.collapsing:
        include_collapsing_params(fh, args.test, args.local)

    # Optionally override ResourceRequirements with smaller values when testing
    # if args.include_resource_overrides:
    #     include_resource_overrides(fh)

    # Include title_file in inputs.yaml
    title_file_obj = {'title_file': {'class': 'File', 'path': args.title_file_path}}
    fh.write(ruamel.yaml.dump(title_file_obj))

    # This file itself is an input to the pipeline,
    # to include version details in the QC PDF
    inputs_yaml_object = {'inputs_yaml': {'class': 'File', 'path': output_file_name}}
    fh.write(ruamel.yaml.dump(inputs_yaml_object))
    include_version_info(fh)

    fh.close()


def include_version_info(fh):
    """
    Todo: Include indentifier to indicate if commit == tag
    """
    import version
    fh.write(INPUTS_FILE_DELIMITER)
    fh.write('version: {} \n'.format(version.most_recent_tag))
    fh.write('# Pipeline Run Version Information: \n')
    fh.write('# Version: {} \n'.format(version.version))
    fh.write('# Short Version: {} \n'.format(version.short_version))
    fh.write('# Most Recent Tag: {} \n'.format(version.most_recent_tag))
    fh.write('# Dirty? {} \n'.format(str(version.dirty)))


def check_final_file(output_file_name):
    """
    Check that lengths of these fields in the final file are equal:
    """
    with open(output_file_name, 'r') as stream:
        final_file = ruamel.yaml.round_trip_load(stream)

    # Todo: Use CONSTANTS
    fields_per_sample = [
        'add_rg_ID',
        'add_rg_LB',
        'add_rg_PU',
        'add_rg_SM',
        'patient_id',
        'fastq1',
        'fastq2',
        'sample_sheet',
        'adapter',
        'adapter2',
    ]

    try:
        for field in fields_per_sample:
            assert len(final_file[field]) == len(final_file['fastq1'])
    except AssertionError:
        print(DELIMITER + 'It looks like there aren\'t enough entries for one of these fields: {}'
              .format(fields_per_sample))
        print('Most likely, one of the samples is missing a read 1 fastq, read 2 fastq and/or sample sheet')


def parse_arguments():
    parser = argparse.ArgumentParser()

    # Required Arguments
    parser.add_argument(
        "-i",
        "--title_file_path",
        help="Title File (generated from create_title_file.py)",
        required=True
    )
    parser.add_argument(
        "-d",
        "--data_dir",
        help="Directory with fastqs and samplesheets",
        required=True
    )

    # Optional Arguments
    parser.add_argument(
        "-t",
        "--test",
        help="Whether to run with test params or production params",
        required=False,
        action="store_true"
    )
    parser.add_argument(
        "-c",
        "--collapsing",
        help="Whether to only generate inputs necessary for standard bams, or to run full pipeline with collapsing.",
        required=False,
        action="store_true"
    )
    parser.add_argument(
        "-l",
        "--local",
        help="Whether to use paths to tool specified for local pipeline operation",
        required=False,
        action="store_true"
    )
    parser.add_argument(
        "-o",
        "--output_file_name",
        help="Name of yaml file for pipeline",
        required=True
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Skip validation",
        required=False,
        action="store_true"
    )
    return parser.parse_args()


def perform_validation(title_file):
    """
    Make sure that we don't have any unacceptable entries in the title file:

    1. Sample IDs must be unique
    2. Barcodes must be unique within each lane
    3. Sample_type is in ['Plasma', 'Buffy Coat']
    4. Sex is one of ['Male, 'M', 'Female', 'F']
    5. Sample Class is in ['Tumor', 'Normal']
    """
    if np.sum(title_file[TITLE_FILE__SAMPLE_ID_COLUMN].duplicated()) > 0:
        raise Exception(DELIMITER + 'Duplicate sample names. Exiting.')

    for lane in title_file[TITLE_FILE__LANE_COLUMN].unique():
        lane_subset = title_file[title_file[TITLE_FILE__LANE_COLUMN] == lane]

        if np.sum(lane_subset[TITLE_FILE__BARCODE_ID_COLUMN].duplicated()) > 0:
            raise Exception(DELIMITER + 'Duplicate barcode IDs. Exiting.')

    if np.sum(title_file[TITLE_FILE__CLASS_COLUMN].isin(['Tumor', 'Normal'])) < len(title_file):
        raise Exception(DELIMITER + 'Not all sample classes are in [Tumor, Normal]')

    if np.sum(title_file[TITLE_FILE__SAMPLE_TYPE_COLUMN].isin(['Plasma', 'Buffy Coat'])) < len(title_file):
        raise Exception(DELIMITER + 'Not all sample types are in [Plasma, Buffy Coat]')


def print_user_message():
    print(DELIMITER)
    print('You\'ve just created the inputs file. Please double check its entries before kicking off a run.')
    print('Common mistakes include:')
    print('1. Trying to use test parameters on a real run (accidentally using the -t param)')
    print('2. Using the wrong bedfile for the capture')
    print('3. Not specifying the \'-c\' parameter when collapsing steps are intended')
    print('4. Working in the wrong virtual environment (are you sure you ran setup.py install?)')
    print('6. Not specifying the correct parameters for logLevel or cleanWorkDir ' +
          '(if you want to see the actual commands passed to the tools, or keep the temp outputs after a successful run)')
    print('7. Do you have the correct PATH variable set (to reference the intended version of BWA during abra realignment?)')
    print('8. The "Sex" column of the title file will only correctly idenfity patients with [Male, M, Female, F] entries.')

########
# Main #
########

def main():
    # Parse arguments
    args = parse_arguments()

    # Read title file
    title_file = pd.read_csv(args.title_file_path, sep='\t')

    # Sort based on Patient ID
    # This is done to ensure that the order of the samples is retained after indel realignment,
    # which groups the samples on a per-patient basis
    # Todo: This requirement / rule needs to be explicitly documented
    title_file = title_file.sort_values(TITLE_FILE__PATIENT_ID_COLUMN).reset_index(drop=True)

    # Perform some sanity checks on the title file
    if not args.force:
        perform_validation(title_file)
    # Create the inputs file for the run
    write_inputs_file(args, title_file, args.output_file_name)
    # Perform some checks on the final yaml file that will be supplied to the pipeline
    check_final_file(args.output_file_name)
    print_user_message()


if __name__ == '__main__':
    main()
