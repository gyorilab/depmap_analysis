"""
Run depmap script on multiple ranges of z-scores and optionally on an open
ended range with the highest z-score as lower bound and/or a random sampling
of all participating entities in the correlation matrix.
"""
import logging

import numpy as np
import argparse
from typing import Optional

import pandas as pd

from depmap_analysis.util.io_functions import file_opener, allowed_types, \
    file_path
from depmap_analysis.post_processing.expl_proportions import _join
from depmap_analysis.scripts.depmap_script2 import main


logger = logging.getLogger(__name__)


def _get_outfile_name(
    prefix: str, lo_sd: Optional[float] = None, hi_sd: Optional[float] = None
) -> str:
    def _get_int_if_int(n: float) -> str:
        # If like int, e.g. 7.0 == 7
        if int(n) == n:
            return str(int(n))
        # Else
        else:
            # Make str and remove ".", then remove
            s = str(n).replace(".", "")
            return s

    # Closed range
    if lo_sd is not None and hi_sd is not None:
        return (
            f"{prefix}_{_get_int_if_int(lo_sd)}_"
            f"{_get_int_if_int(hi_sd)}.pkl"
        )
    # Open range upwards
    elif lo_sd is not None and hi_sd is None:
        return f"{prefix}_{_get_int_if_int(lo_sd)}_.pkl"
    # Open range downwards
    elif lo_sd is None and hi_sd is not None:
        return f"{prefix}_{_get_int_if_int(hi_sd)}.pkl"
    # Random
    elif lo_sd is None and hi_sd is None:
        return f"{prefix}_rnd.pkl"
    else:
        raise ValueError("This should not happen")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "DepMap Explainer meta script", fromfile_prefix_chars="@"
    )

    # sd ranges
    parser.add_argument(
        "--sd-ranges",
        type=float,
        nargs=3,
        required=True,
        help="Provide <start> <stop> <# ranges> for SD ranges. <# ranges> "
        'will be made an int via int(). Examples: providing "0 5 5" will '
        "give 5 ranges of equal width from 0 to 5: 0-1, 1-2, 2-3, 3-4, "
        '4-5, while providing "3 8 10" gives 10 ranges of width 0.5 '
        "from 3 to 8: 3-3.5, 3.5-4, 4-4.5, 4.5-5, 5-5.5, 5.5-6, 6-6.5, "
        "6.5-7, 7-7.5, 7.5-8.",
    )

    # do rnd sampling?
    parser.add_argument(
        "--random", action="store_true", help="Also run a random sampling"
    )

    # graph
    parser.add_argument(
        "--graph",
        type=file_path(".pkl"),
        required=True,
        help="The graph to match correlations with",
    )

    # Outpath
    parser.add_argument(
        "--outpath",
        required=True,
        help="The output name prefix of the pickle dump of the explainer "
        "object. The name can be a path as well as an S3 url, e.g. "
        "s3://my_bucket/dir1/dir2/. The final output path "
        "per explainer object will be of the form "
        "<outpath>/<graph type>_<lo sd>",
    )

    # graph type
    allowed_graph_types = {"unsigned", "signed"}
    parser.add_argument(
        "--graph-type",
        type=allowed_types(allowed_graph_types),
        default="unsigned",
        help=f"Specify the graph type used. Allowed values are "
        f"{allowed_graph_types}",
    )

    # corr matrix
    parser.add_argument(
        "--z-score",
        type=file_path(".h5"),
        help="The file path to the fully merged correlation matrix "
        "containing z-scores for gene-gene correlations.",
    )

    # sample size = 100000
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100000,
        help="If provided, down sample the correlation matrix so this many "
        "pairs (approximately) are picked at random.",
    )

    # overwrite
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If provided, down sample the correlation matrix so this many "
        "pairs (approximately) are picked at random.",
    )

    # Open range on last
    parser.add_argument(
        "--open-range",
        action="store_true",
        help="If set, run the range/interval z-score > <stop>",
    )

    # chunks = 1
    parser.add_argument(
        "--chunks",
        type=int,
        default=1,
        help="Set the number of chunks to split the data into to run "
        "multiprocessing. If set to e.g. 4, 4 workers will be started "
        "to run async with multiprocessing.Pool.apply_async. If set to "
        "1 (default), no multiprocessing will be used.",
    )

    args = parser.parse_args()

    # defaults not up to user:
    #   - shuffle the stuff
    #   - explanation functions

    # Load graph
    graph = file_opener(args.graph)

    # Load corr
    logger.info(f"Loading z-score dataframe {args.z_score}")
    z_corr = pd.read_hdf(args.z_score)
    logger.info("Done loading dataframe")

    # Set kwargs
    kwargs = dict(
        indra_net=graph,
        z_score=z_corr,
        graph_type=args.graph_type,
        expl_funcs=[
            "apriori_explained",
            "common_reactome_paths",
            "find_cp",
            "parent_connections",
            "expl_axb",
            "expl_bxa",
            "get_sr",
            "get_st",
            "expl_ab",
            "expl_ba",
        ],
        n_chunks=args.chunks,
        immediate_only=True,
        return_unexplained=False,
        reactome_path="s3://depmap-analysis/misc_files/reactome_pathways.pkl",
        apriori_explained=True,
        allowed_ns=["fplx", "hgnc"],
        sample_size=args.sample_size,
        shuffle=True,
        overwrite=args.overwrite,
        normalize_names=False,
        indra_net_path=args.graph,
        z_score_path=args.z_score,
    )

    start, end, num = args.sd_ranges
    ranges = np.linspace(start, end, int(num) + 1)
    outname = _join(args.outpath, args.graph_type)

    for lo, hi in zip(ranges[:-1], ranges[1:]):
        outfile = _get_outfile_name(outname, lo, hi)
        try:
            main(sd_range=(lo, hi), random=False, outname=outfile, **kwargs)
        except FileExistsError as err:
            logger.exception(err)
            logger.error(
                f"Script running on range {lo}-{hi} failed. Output "
                f"seems to exist already. Use flag --overwrite to "
                f"force a new script run."
            )
            continue

    # Run last range as open ended
    if args.open_range:
        outfile = _get_outfile_name(outname, end)
        main(sd_range=(end, None), random=False, outname=outfile, **kwargs)

    if args.random:
        outfile = _get_outfile_name(outname)
        main(sd_range=tuple(), random=True, outname=outfile, **kwargs)
