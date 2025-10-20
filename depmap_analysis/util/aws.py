import re
import json
import pickle
import logging
from typing import Union, Tuple, Any, Dict, Optional
from operator import itemgetter

from indra.config import get_config
from indra.util.aws import get_s3_file_tree, get_s3_client


logger = logging.getLogger(__name__)

DUMPS_BUCKET = get_config("DUMPS_BUCKET") or 'bigmech'
DUMPS_PREFIX = 'indra-db/dumps/'
NET_BUCKET = get_config("NET_BUCKET") or 'depmap-analysis'
NETS_PREFIX = 'graphs/'
NETS_SOURCE_DATA_PREFIX_SUBDIR = "source_data"
SIF_PKL_NAME = "sif.pkl"
STMT_HASH_MESH_PKL_NAME = "statement_hash_mesh_id.pkl"


def get_latest_sif_s3(
    get_mesh_ids: bool = False
) -> Union[Tuple[Any, str], Tuple[Tuple[Any, str], Tuple[Any, str]]]:
    necc_files = [SIF_PKL_NAME]
    if get_mesh_ids:
        necc_files.append(STMT_HASH_MESH_PKL_NAME)
    s3 = get_s3_client(unsigned=False)
    tree = get_s3_file_tree(
        s3, bucket=NET_BUCKET, prefix=NETS_PREFIX, with_dt=True
    )
    # Find all pickles
    keys = [key for key in tree.gets('key') if key[0].endswith('.pkl')]
    # Sort newest first
    keys.sort(key=lambda t: t[1], reverse=True)
    # Get keys of those pickles
    keys_in_latest_dir = [
        k[0] for k in keys if any(nfl in k[0] for nfl in necc_files)
    ]
    # Map key to resource
    necc_keys = {}
    for n in necc_files:
        for k in keys_in_latest_dir:
            # check name then alt name
            if n in k:
                # Save and continue to next file in necc_files
                necc_keys[n] = k
                break
    logger.info(f'Latest files: {", ".join([f for f in necc_keys.values()])}')
    sif_key = necc_keys[SIF_PKL_NAME]
    df = load_pickle_from_s3(s3, key=sif_key, bucket=NET_BUCKET)
    sif_date = _get_date_from_s3_key(sif_key)
    if get_mesh_ids:
        hash_mesh_key = necc_keys[STMT_HASH_MESH_PKL_NAME]
        mid = load_pickle_from_s3(s3, key=hash_mesh_key, bucket=NET_BUCKET)
        meshids_date = _get_date_from_s3_key(hash_mesh_key)
        return (df, sif_date), (mid, meshids_date)

    return df, sif_date


def _get_date_from_s3_key(s3key: str) -> str:
    # Checks if path is in the expected format
    # Example: "graphs/2023-10-01/source_data/sif.pkl"
    patt = re.compile(
        NETS_PREFIX + "([0-9\-]+)/"+ NETS_SOURCE_DATA_PREFIX_SUBDIR + "/(.*)"
    )
    m = patt.match(s3key)
    if m is None:
        raise ValueError(f'Invalid format for s3 path: {s3key}')

    # Split and get date from path
    date_str, fname = m.groups()
    logger.info(f"Got date {date_str} for {fname} from s3 key {s3key}")
    return date_str


def load_pickle_from_s3(s3, key, bucket):
    try:
        res = s3.get_object(Key=key, Bucket=bucket)
        pyobj = pickle.loads(res['Body'].read())
        logger.info('Finished loading pickle from s3')
    except Exception as err:
        logger.error('Something went wrong while loading, reading or '
                     'unpickling the object from s3')
        raise err
    return pyobj


def dump_json_to_s3(name: str, json_obj: Dict, public: bool = False,
                    get_url: bool = False) -> Optional[str]:
    """Dumps a json object to S3

    Parameters
    ----------
    name :
        The file name to use for the uploaded file. Appropriate prefixes
        will be used.
    json_obj :
        The json object to upload
    public :
        If True allow public read access. Default: False.
    get_url :
        If True return the S3 url of the object

    Returns
    -------
    :
        Optionally return the S3 url of the json file
    """
    s3 = get_s3_client(unsigned=False)
    key = 'indra_network_search/' + name
    options = {'Bucket': DUMPS_BUCKET,
               'Key': key}
    if public:
        options['ACL'] = 'public-read'
    s3.put_object(Body=json.dumps(json_obj), **options)
    if get_url:
        return s3.generate_presigned_url(
            'get_object', Params={'Key': key, 'Bucket': DUMPS_BUCKET})


def read_json_from_s3(s3, key, bucket):
    try:
        res = s3.get_object(Key=key, Bucket=bucket)
        json_obj = json.loads(res['Body'].read().decode())
        logger.info('Finished loading json from s3')
    except Exception as err:
        logger.error('Something went wrong while loading or reading the json '
                     'object from s3')
        raise err
    return json_obj


def dump_pickle_to_s3(name, pyobj, prefix=''):
    s3 = get_s3_client(unsigned=False)
    key = prefix + name
    key = key.replace('//', '/')
    s3.put_object(Bucket=NET_BUCKET, Key=key,
                  Body=pickle.dumps(obj=pyobj))


def get_latest_pa_stmt_dump():
    s3_cli = get_s3_client(False)
    # Get file key
    dump_name = 'full_pa_stmts.pkl'
    file_tree = get_s3_file_tree(s3=s3_cli,
                                 bucket=DUMPS_BUCKET,
                                 prefix=DUMPS_PREFIX,
                                 with_dt=True)
    # Get all keys for dump_name
    keys = [key for key in file_tree.gets('key') if key[0].endswith(dump_name)]
    keys.sort(key=itemgetter(1))  # Sorts ascending by datetime

    return load_pickle_from_s3(s3_cli, keys[-1][0], DUMPS_BUCKET)
