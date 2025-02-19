import argparse
import logging
from pathlib import Path
from typing import Dict, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.special import ndtri_exp
from tqdm import tqdm

from depmap_analysis.explainer import DepMapExplainer
from depmap_analysis.post_processing.util import get_dir_iter
from depmap_analysis.util.io_functions import is_dir_path, file_opener

logger = logging.getLogger(__name__)

# Parameters to care about:
# 1. Graph type
# 2. SD ranges
# 3. Type of explanations


def thousands(n: int) -> str:
    """Turn an int to a string of its value per 1000

    Parameters
    ----------
    n :
        Number to turn into a string representation of in parts per
        thousand, unless number is < 1000.

    Returns
    -------
    :
    """
    if n < 1000:
        return str(n)
    else:
        return str(n // 1000) + 'k'


def _get_expl_data(dme: DepMapExplainer) -> Dict[str, Union[str, int, float]]:
    global labels
    sumd = dme.get_summary()
    tot = sumd['total checked']
    data = {k: 100 * v / tot for k, v in sumd.items() if k in labels}
    lo, hi = dme.sd_range
    if lo:
        lon = int(lo) if int(lo) == lo else lo
    else:
        lon = lo
    if hi:
        hin = str(int(hi)) if int(hi) == float(hi) else hi
    else:
        hin = hi
    rand = dme.script_settings['random']
    data['range'] = 'RND' if rand else \
        (f'{lon}-{hin}' if hin else f'{lon}+')
    data['filter_w_count'] = data['range'] + '\n' + thousands(tot)
    data['x_pos'] = -1 if rand else lon

    return data


def _loop_explainers(expl_path: str):
    # Store explainer data by their graph type
    expl_by_type = {'pybel': [],
                    'signed': [],
                    'unsigned': []}
    for explainer_file in tqdm(get_dir_iter(expl_path, '.pkl')):
        expl: DepMapExplainer = file_opener(explainer_file)
        expl_data = _get_expl_data(expl)
        expl_by_type[expl.script_settings['graph_type']].append(expl_data)

    return expl_by_type


def main():
    logger.info('Extracting data from explainers')
    expl_data = _loop_explainers(expl_dir)

    # Per graph type, extract what the old code has
    for graph_type, list_of_expl_data in expl_data.items():
        if len(list_of_expl_data) == 0:
            logger.info(f'Skipping graph type {graph_type}')
            continue
        logger.info(f'Plotting for graph type {graph_type}')
        stats_norm = pd.DataFrame(
            columns=['range', 'filter_w_count', 'x_pos'] + labels
        )

        for data in list_of_expl_data:
            stats_norm = stats_norm.append(other=pd.DataFrame(data=data,
                                                              index=[0]),
                                           sort=False)
        stats_norm.sort_values('x_pos', inplace=True)

        # Plot
        stats_norm.plot(x='x_pos',
                        y=labels,
                        legend=legend_labels,
                        kind='line',
                        marker='o',
                        title=f'{data_title}, {graph_type.capitalize()}')
        ticks = [-1] + list(range(int(stats_norm.x_pos.values[1]),
                                  int(stats_norm.x_pos.max()) + 2, 2))
        ticks_labels = ['RND'] + [str(n) for n in ticks[1:]]
        fdr_line = abs(ndtri_exp(np.log(0.05)) - np.log(2))  # <-- WRONG, fixme
        fdr_label = 'FDR=|ndtri_exp(ln(.05)-ln(2))|'
        plt.xticks(ticks=ticks, labels=ticks_labels)
        plt.xlabel('abs(z-score) lower bound')
        plt.ylabel('Pct. Corrs. Explained')
        plt.ylim((0, 100))
        plt.axvline(x=fdr_line, ymax=0.65, color='c', label=fdr_label)
        plt.legend()
        fpath = Path(outdir).joinpath(f'{data_title}_{graph_type}.pdf')
        logger.info(f'Saving plot output to {fpath}')
        plt.savefig(fpath)
        if args.show_plot:
            plt.show()

        stats_norm.plot(x='x_pos',
                        y=labels,
                        legend=legend_labels,
                        kind='line',
                        marker='o',
                        logy=True,
                        title=f'{data_title}, '
                              f'{graph_type.capitalize()} (ylog)')
        plt.xticks(ticks=ticks, labels=ticks_labels)
        plt.xlabel('abs(z-score) lower bound')
        plt.ylabel('Pct. Corrs. Explained')
        plt.ylim((10 ** -2, 10 ** 2))
        plt.axvline(x=fdr_line, ymin=0.35, color='c', label=fdr_label)
        plt.legend()
        plt.savefig(
            Path(outdir).joinpath(f'{data_title}_{graph_type}_ylog.pdf'))
        if args.show_plot:
            plt.show()


def _join(d: str, s: str) -> str:
    if d.endswith('/') and s.startswith('/'):
        return d + s[1:]
    elif d.endswith('/') and not s.startswith('/') or \
            not d.endswith('/') and s.startswith('/'):
        return d + s
    else:
        return d + '/' + s


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', required=True,
                        help='Title for data (will also be used as plot '
                             'output name)')
    total_col = 'total checked'
    default_cols = ['explained (excl sr)', 'complex or direct',
                    'apriori_explained',
                    'explained no reactome, direct, apriori']
    parser.add_argument('--columns', nargs='+',
                        default=default_cols,
                        help=f'Specify columns to plot. '
                             f'Default: {default_cols}')
    parser.add_argument('--explainer-dir', type=is_dir_path(), required=True,
                        help='The explainer files live here. No other pickle '
                             'files should be present. Path can be S3 url.')
    parser.add_argument('--labels', nargs='+',
                        help='Legend labels on plot (corresponding to column '
                             'names). Default: column names')
    parser.add_argument('--outdir',
                        help='Directory where to put the saved figure. '
                             'Default is same directory as value of '
                             '--explainer-dir .')
    parser.add_argument('--show-plot', action='store_true',
                        help='Show the generated plots will be shown as well '
                             'as saved')

    args = parser.parse_args()
    expl_dir: str = args.explainer_dir
    outdir = args.outdir if args.outdir else _join(expl_dir, 'prop_plots')
    logger.info(f'Output path set to {outdir}')

    # Create local output path if it doesn't exist
    if not outdir.startswith('s3://') and not Path(outdir).is_dir():
        Path(outdir).mkdir(parents=True)

    data_title = args.title
    labels = args.columns
    labels = labels if len(labels) > 0 else default_cols
    legend_labels = [n.replace('_', ' ') for n in
                     (args.labels if args.labels else labels)]
    logger.info(f'Using legend labels: {" ".join(legend_labels)}')

    main()
