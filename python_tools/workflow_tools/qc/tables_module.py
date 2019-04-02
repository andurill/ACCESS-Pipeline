#!python

##################################################
# ACCESS QC Module
# Innovation Laboratory
# Center For Molecular Oncology
# Memorial Sloan Kettering Cancer Research Center
# maintainer: Ian Johnson (johnsoni@mskcc.org)
##################################################

import logging
import argparse
import numpy as np
import pandas as pd

from ...constants import *


#####################
# Helper methods
# todo: refactor away
#####################

def unique_or_tot(x):
    if TOTAL_LABEL in x:
        return TOTAL_LABEL
    else:
        return PICARD_LABEL


##########################
# Table creation methods #
##########################

def get_read_counts_table(path, pool):
    """
    This method is only used to generate stats for un-collapsed bams
    """
    read_counts_path = os.path.join(path, AGBM_READ_COUNTS_FILENAME)
    read_counts = pd.read_csv(read_counts_path, sep='\t')
    # Melt our DF to get all values of the on target rate and duplicate rates as values
    read_counts = pd.melt(read_counts, id_vars=[SAMPLE_ID_COLUMN], var_name='Category')
    # We only want the read counts-related row values
    read_counts = read_counts[~read_counts['Category'].isin(['bam', TOTAL_READS_COLUMN, UNMAPPED_READS_COLUMN, 'duplicate_fraction'])]
    read_counts['method'] = read_counts['Category'].apply(unique_or_tot)
    read_counts['pool'] = pool
    # read_counts = read_counts.reset_index(drop=True)

    return read_counts


def get_read_counts_total_table(path, pool):
    """
    This table is used for "Fraction of Total Reads that Align to the Human Genome" plot
    """
    full_path = os.path.join(path, AGBM_READ_COUNTS_FILENAME)
    read_counts_total = pd.read_csv(full_path, sep='\t')

    col_idx = ~read_counts_total.columns.str.contains(PICARD_LABEL)

    read_counts_total = read_counts_total.iloc[:, col_idx]
    read_counts_total['AlignFrac'] = read_counts_total[TOTAL_MAPPED_COLUMN] / read_counts_total[TOTAL_READS_COLUMN]
    read_counts_total[TOTAL_OFF_TARGET_FRACTION_COLUMN] = 1 - read_counts_total[TOTAL_ON_TARGET_FRACTION_COLUMN]

    read_counts_total['pool'] = pool
    return read_counts_total


def get_coverage_table(path, pool):
    """
    Coverage table
    """
    full_path = os.path.join(path, AGBM_COVERAGE_FILENAME)
    coverage_table = pd.read_csv(full_path, sep='\t')
    coverage_table = pd.melt(coverage_table, id_vars=SAMPLE_ID_COLUMN, var_name='method', value_name='average_coverage')
    coverage_table['method'] = coverage_table['method'].str.replace('average_coverage_', '')
    coverage_table['pool'] = pool
    return coverage_table


def get_collapsed_waltz_tables(path, method, pool):
    """
    Creates read_counts, coverage, and gc_bias tables for collapsed bam metrics.
    """
    read_counts_table_path = os.path.join(path, AGBM_READ_COUNTS_FILENAME)
    read_counts_table = pd.read_csv(read_counts_table_path, sep='\t')
    read_counts_table = pd.melt(read_counts_table, id_vars=[SAMPLE_ID_COLUMN], var_name='Category')
    read_counts_table = read_counts_table.dropna(axis=0)
    read_counts_table['method'] = [method] * len(read_counts_table)
    read_counts_table['pool'] = pool

    # Todo: merge with get_cov_table
    coverage_table_path = '/'.join([path, AGBM_COVERAGE_FILENAME])
    coverage_table = pd.read_csv(coverage_table_path, sep='\t', usecols=[0, 1], names=[SAMPLE_ID_COLUMN, 'average_coverage'], header=0)
    coverage_table['method'] = [method] * len(coverage_table)
    coverage_table['pool'] = pool

    gc_bias_table = get_gc_table(method, WALTZ_INTERVALS_FILENAME_SUFFIX, path)

    return [read_counts_table, coverage_table, gc_bias_table]


def get_gc_table(curr_method, intervals_filename_suffix, path):
    """
    Function to create GC content table
    """
    gc_with_cov = pd.DataFrame(columns=GC_BIAS_HEADER)
    sample_files = [f for f in os.listdir(path) if intervals_filename_suffix in f]

    for sample in sample_files:
        filename = os.path.join(path, sample)
        curr_table = pd.read_csv(filename, names=WALTZ_INTERVALS_FILE_HEADER, sep='\t')
        sample = sample.split('_cl_aln_srt')[0]

        newDf = curr_table[[WALTZ_INTERVAL_NAME_COLUMN, WALTZ_PEAK_COVERAGE_COLUMN, WALTZ_GC_CONTENT_COLUMN]].copy()
        newDf['method'] = curr_method
        newDf[SAMPLE_ID_COLUMN] = sample
        gc_with_cov = pd.concat([gc_with_cov, newDf]).sort_values([SAMPLE_ID_COLUMN, WALTZ_INTERVAL_NAME_COLUMN])

    return gc_with_cov


def get_bins(tbl):
    """
    Create bins from min_gc value to max_gc value in increments of 0.05 (for GC content table)
    """
    logging.info('GC table generation')
    logging.info(tbl)

    min_gc = np.min(tbl['gc'])
    max_gc = np.max(tbl['gc'])
    start = round(min_gc - np.mod(min_gc, 0.05), 2)
    stop = round(max_gc + 0.1 - np.mod(max_gc, 0.05), 2)
    all_bins = np.arange(start, stop, step=0.05)
    return all_bins


def get_gc_table_average_for_each_sample(tbl):
    """
    Creates the GC content table, with each sample represented
    """
    tbl = tbl.copy()

    # Restrict to just 0.3 --> 0.8 %GC
    all_bins = np.arange(0.3, 0.85, 0.05)
    tbl[GC_BIN_COLUMN] = pd.cut(tbl['gc'], all_bins)

    # Create new column of normalized coverage across intervals, for each combination of sample and method
    groups = [METHOD_COLUMN, SAMPLE_ID_COLUMN]
    grouped = tbl.groupby(groups)['peak_coverage']
    tbl['coverage_norm'] = grouped.transform(lambda x: x / x.mean())

    # Calculate mean coverage within each GC bin, after standardizing coverage across whole sample
    groups = [METHOD_COLUMN, SAMPLE_ID_COLUMN, GC_BIN_COLUMN]
    grouped = tbl.groupby(groups)['coverage_norm']
    tbl['coverage_norm_2'] = grouped.transform(lambda x: x.mean())

    tbl = tbl[[SAMPLE_ID_COLUMN, 'coverage_norm_2', GC_BIN_COLUMN, METHOD_COLUMN]].copy()
    tbl = tbl.drop_duplicates()
    tbl = tbl.rename(index=str, columns={'coverage_norm_2': 'coverage'})

    tbl = tbl[~tbl.isnull().any(axis=1)]
    return tbl


def get_gene_and_probe(interval):
    gene_interval_regex = re.compile(r'^.*_.*_.*_.*$')

    # Example interval string: exon_AKT1_4a_1
    if interval[0:4] == 'exon':
        split = interval.split('_')
        return split[1], split[2] + '_' + split[3]

    # Another example I've encountered: 426_2903_324(APC)_1a
    elif gene_interval_regex.match(interval):
        split = interval.split('_')
        return '_'.join(split[0:2]), '_'.join(split[2:4])

    else:
        gene, exon = interval.split('_exon_')
        return gene, exon


def get_coverage_per_interval(tbl):
    """
    Creates table of collapsed coverage per interval
    """
    # Coverage per interval Graph comes from unfiltered Bam, Pool A Targets
    unfiltered_boolv = (tbl['method'] == UNFILTERED_COLLAPSING_METHOD)

    # Filter out MSI & Fingerprinting intervals
    exon_boolv = ['exon' in y for y in tbl[WALTZ_INTERVAL_NAME_COLUMN]]
    relevant_coverage_columns = [WALTZ_PEAK_COVERAGE_COLUMN, WALTZ_INTERVAL_NAME_COLUMN, SAMPLE_ID_COLUMN]
    final_tbl = tbl[unfiltered_boolv & exon_boolv][relevant_coverage_columns]

    # Add on new gene and probe columns
    gene_probe = [get_gene_and_probe(val) for val in final_tbl[WALTZ_INTERVAL_NAME_COLUMN]]
    gene_probe_df = pd.DataFrame(gene_probe, columns=['Gene', 'Probe'])
    # Todo: most likely, the reset_index() calls are unnecessary
    final_tbl = final_tbl.reset_index(drop=True)
    final_tbl = pd.concat([final_tbl, gene_probe_df], axis=1)
    final_tbl = final_tbl.reset_index(drop=True)

    return final_tbl


def get_coverage_per_interval_exon_level(tbl):
    """
    Exon-Level Coverage per Interval Graph comes from Duplex Bam, Pool A Targets
    """
    total_boolv = (tbl['method'] == DUPLEX_COLLAPSING_METHOD)
    final_tbl = tbl[total_boolv]
    return final_tbl


########
# Main #
########

def main():
    """
    This method is kept separate to allow for testing of the create_combined_qc_tables() method,
    using a mock argparse object

    :return:
    """
    parser = argparse.ArgumentParser(description='MSK ACCESS QC module', formatter_class=argparse.RawTextHelpFormatter)

    # Probe-level QC files, A-Targets
    parser.add_argument('-swa', '--standard_waltz_pool_a', type=str, default=None, required=True, action=FullPaths)
    parser.add_argument('-mua', '--unfiltered_waltz_pool_a', type=str, default=None, action=FullPaths)
    parser.add_argument('-msa', '--simplex_waltz_pool_a', type=str, default=None, action=FullPaths)
    parser.add_argument('-mda', '--duplex_waltz_pool_a', type=str, default=None, action=FullPaths)

    # Probe-level QC files, B-Targets
    parser.add_argument('-swb', '--standard_waltz_pool_b', type=str, default=None, required=True, action=FullPaths)
    parser.add_argument('-mub', '--unfiltered_waltz_pool_b', type=str, default=None, action=FullPaths)
    parser.add_argument('-msb', '--simplex_waltz_pool_b', type=str, default=None, action=FullPaths)
    parser.add_argument('-mdb', '--duplex_waltz_pool_b', type=str, default=None, action=FullPaths)

    # Exon-level QC files, A-Targets
    parser.add_argument('-swael', '--standard_waltz_metrics_pool_a_exon_level', type=str, default=None, action=FullPaths)
    parser.add_argument('-muael', '--unfiltered_waltz_metrics_pool_a_exon_level', type=str, default=None, action=FullPaths)
    parser.add_argument('-msael', '--simplex_waltz_metrics_pool_a_exon_level', type=str, default=None, action=FullPaths)
    parser.add_argument('-mdael', '--duplex_waltz_metrics_pool_a_exon_level', type=str, default=None, action=FullPaths)

    args = parser.parse_args()
    create_combined_qc_tables(args)


def create_combined_qc_tables(args):
    """
    Read in and concatenate all the tables from their respective waltz output folders

    Write these tables to the current directory

    :param args: argparse.ArgumentParser with parsed arguments
    :return:
    """
    read_counts_total_pool_a_table = get_read_counts_total_table(args.standard_waltz_pool_a, POOL_A_LABEL)
    read_counts_total_pool_b_table = get_read_counts_total_table(args.standard_waltz_pool_b, POOL_B_LABEL)
    read_counts_total_table = pd.concat([read_counts_total_pool_a_table, read_counts_total_pool_b_table])

    # Standard, Pools A and B
    pool_a_read_counts = get_read_counts_table(args.standard_waltz_pool_a, POOL_A_LABEL)
    pool_a_coverage_table = get_coverage_table(args.standard_waltz_pool_a, POOL_A_LABEL)
    gc_cov_int_table = get_gc_table(TOTAL_LABEL, WALTZ_INTERVALS_FILENAME_SUFFIX, args.standard_waltz_pool_a)
    pool_b_read_counts = get_read_counts_table(args.standard_waltz_pool_b, POOL_B_LABEL)
    read_counts_table = pd.concat([pool_b_read_counts, pool_a_read_counts])
    pool_b_coverage_table = get_coverage_table(args.standard_waltz_pool_b, POOL_B_LABEL)
    coverage_table = pd.concat([pool_b_coverage_table, pool_a_coverage_table])

    ##############
    # Pool-Level #
    # A Targets  #
    ##############
    unfilt = get_collapsed_waltz_tables(args.unfiltered_waltz_pool_a, UNFILTERED_COLLAPSING_METHOD, POOL_A_LABEL)
    simplex = get_collapsed_waltz_tables(args.simplex_waltz_pool_a, SIMPLEX_COLLAPSING_METHOD, POOL_A_LABEL)
    duplex = get_collapsed_waltz_tables(args.duplex_waltz_pool_a, DUPLEX_COLLAPSING_METHOD, POOL_A_LABEL)
    read_counts_table = pd.concat([read_counts_table, unfilt[0], simplex[0], duplex[0]]).reset_index(drop=True)
    coverage_table = pd.concat([coverage_table, unfilt[1], simplex[1], duplex[1]]).reset_index(drop=True)
    gc_cov_int_table = pd.concat([gc_cov_int_table, unfilt[2], simplex[2], duplex[2]]).reset_index(drop=True)

    ##############
    # Pool-Level #
    # B Targets  #
    ##############
    unfilt = get_collapsed_waltz_tables(args.unfiltered_waltz_pool_b, UNFILTERED_COLLAPSING_METHOD, POOL_B_LABEL)
    simplex = get_collapsed_waltz_tables(args.simplex_waltz_pool_b, SIMPLEX_COLLAPSING_METHOD, POOL_B_LABEL)
    duplex = get_collapsed_waltz_tables(args.duplex_waltz_pool_b, DUPLEX_COLLAPSING_METHOD, POOL_B_LABEL)
    read_counts_table = pd.concat([read_counts_table, unfilt[0], simplex[0], duplex[0]]).reset_index(drop=True)
    coverage_table = pd.concat([coverage_table, unfilt[1], simplex[1], duplex[1]]).reset_index(drop=True)

    # Use base tables to create additional tables
    gc_avg_table_each = get_gc_table_average_for_each_sample(gc_cov_int_table)
    coverage_per_interval_table = get_coverage_per_interval(gc_cov_int_table)

    ##############
    # Exon-Level #
    # A Targets  #
    ##############
    gc_cov_int_table_exon_level = get_gc_table(TOTAL_LABEL, WALTZ_INTERVALS_FILENAME_SUFFIX, args.standard_waltz_metrics_pool_a_exon_level)

    unfilt = get_collapsed_waltz_tables(args.unfiltered_waltz_metrics_pool_a_exon_level, UNFILTERED_COLLAPSING_METHOD, POOL_A_LABEL)
    simplex = get_collapsed_waltz_tables(args.simplex_waltz_metrics_pool_a_exon_level, SIMPLEX_COLLAPSING_METHOD, POOL_A_LABEL)
    duplex = get_collapsed_waltz_tables(args.duplex_waltz_metrics_pool_a_exon_level, DUPLEX_COLLAPSING_METHOD, POOL_A_LABEL)
    read_counts_table_exon_level = pd.concat([unfilt[0], simplex[0], duplex[0]]).reset_index(drop=True)
    coverage_table_exon_level = pd.concat([unfilt[1], simplex[1], duplex[1]]).reset_index(drop=True)
    gc_cov_int_table_exon_level = pd.concat([gc_cov_int_table_exon_level, unfilt[2], simplex[2], duplex[2]]).reset_index(drop=True)

    # Use base tables to create additional tables
    gc_avg_table_each_exon_level = get_gc_table_average_for_each_sample(gc_cov_int_table_exon_level)
    # coverage_per_interval_table_exon_level = get_coverage_per_interval_exon_level(gc_cov_int_table_exon_level)

    ####################
    # Write all tables #
    ####################
    read_counts_table.to_csv(read_counts_filename, sep='\t', index=False)
    read_counts_total_table.to_csv(read_counts_total_filename, sep='\t', index=False)
    coverage_table.to_csv(coverage_agg_filename, sep='\t', index=False)
    gc_cov_int_table.to_csv(gc_bias_with_coverage_filename, sep='\t', index=False)
    gc_avg_table_each.to_csv(gc_avg_each_sample_coverage_filename, sep='\t', index=False)
    coverage_per_interval_table.to_csv(coverage_per_interval_filename, sep='\t', index=False)

    read_counts_table_exon_level.to_csv(read_counts_table_exon_level_filename, sep='\t', index=False)
    coverage_table_exon_level.to_csv(coverage_table_exon_level_filename, sep='\t', index=False)
    gc_cov_int_table_exon_level.to_csv(gc_cov_int_table_exon_level_filename, sep='\t', index=False)
    gc_avg_table_each_exon_level.to_csv(gc_avg_each_sample_coverage_exon_level_filename, sep='\t', index=False)

    # Fragment Sizes graph comes from Unfiltered Bam, Pool A Targets
    # Also need waltz-coverage.txt from Duplex A, exon-level metrics
    # todo: not clean
    import shutil
    frag_sizes_path = os.path.join(args.unfiltered_waltz_pool_a, 'fragment-sizes.txt')
    shutil.copyfile(frag_sizes_path, '%s/%s' % ('.', 'fragment_sizes_unfiltered_A_targets.txt'))
    average_coverage_across_exon_targets_path = os.path.join(args.duplex_waltz_metrics_pool_a_exon_level, 'waltz-coverage.txt')
    shutil.copyfile(average_coverage_across_exon_targets_path, '%s/%s' % ('.', 'average_coverage_across_exon_targets_duplex_A.txt'))


class FullPaths(argparse.Action):
    """
    Expand user and relative-paths
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))
