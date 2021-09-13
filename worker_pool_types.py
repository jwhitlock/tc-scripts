#!/usr/bin/env python3

from collections import defaultdict
from collections.abc import Mapping
from csv import DictWriter
from datetime import datetime, timezone
import argparse
import json
import logging
import re
import sys

import taskcluster

logger = logging.getLogger(__name__)


def main(
        auth_options,
        verbose=False,
        json_file=None,
        from_json_file=None,
        csv_file=None,
        full_csv_datetimes=False,
        csv_set=None,
    ):
    """
    Collect and summarize worker data for a pool

    auth_options - Options, such as output of taskcluster.optionsFromEnvironment()
    verbose - True to log progress messages
    json_file - Path to a file to store worker pool data as JSON
    from_json_file - Load worker pool data from a JSON file instead of API
    csv_file - Path to a file to store worker data as a CSV
    full_csv_datetimes - If True, keep microseconds and timezones on dates.
      This may prevent them from being interpreted as dates by spreadsheet
      programs.
    csv_set - A identifer for a restricted set of CSV output columns
    """
    if from_json_file:
        with open(from_json_file, 'r') as the_file:
            pools = json.load(the_file)
        if verbose:
            logger.info("Loaded {len(pools)} worker pools from {from_json_file}.")
    else:
        worker_manager = taskcluster.WorkerManager(auth_options)
        worker_manager.ping()
        if verbose:
            logger.info("Worker Manager is available.")

        pools = get_worker_pools(worker_manager, verbose=verbose)
        if verbose:
            logger.info(f"Fetched {len(pools)} worker pools.")

    if csv_file:
        if verbose:
            logger.info(f"Writing worker pool data to {csv_file}...")
        with open(csv_file, 'w', newline='') as the_file:
            to_csv(pools, the_file, full_csv_datetimes, csv_set)
        if verbose:
            logger.info(f"Done writing {csv_file}.")

    if json_file:
        with open(json_file, 'w') as the_file:
            json.dump(pools, the_file)
        if verbose:
            logger.info(f"Wrote JSON worker pool data to {json_file}.")

    print(worker_pool_summary(pools))

    return 0


def get_worker_pools(worker_manager, verbose=False):
    """Get the workers in a pool, following pagination"""

    page = worker_manager.listWorkerPools()
    page_count = 1
    token = page.get('continuationToken', None)
    pools = page['workerPools']
    if verbose:
        logger.info(f"Getting worker pools, page 1, {len(pools)} pools...")
    while token:
        page = worker_manager.listWorkerPools(
            pool_id, query={'continuationToken': token})
        token = page.get('continuationToken', None)
        pools.extend(page.get('workerPools', []))
        page_count += 1
        if verbose:
            logger.info(f"Getting worker pools, page {page_count}, {len(pools)} pools...")
    if verbose:
        logger.info(f"Found {len(pools)} worker pools.")
    return pools

CSV_SET = {
    "amis": {
        "description": "Determine unique AMIs",
        "columns": [
            "workerPoolId",
            "providerId",
            "created",
            "lastModified",
            "owner",
            "lc_launchConfig_ImageId",
            "lc_region",
            "lc_disks_0_initializeParams_sourceImage",
        ],
    }
}

RE_DATETIME = re.compile(r"""
^(?P<year>[0-9]{4})-    # Year, followed by dash
(?P<month>[01][0-9])-   # Month, followed by dash
(?P<day>[0-3][0-9])T    # Day, followed by T
(?P<hour>[0-5][0-9]):   # Hour, followed by colon
(?P<minute>[0-5][0-9]): # Minute, followed by colon
(?P<second>[0-5][0-9])  # Second
\.?                     # Optional period
(?P<msecond>[0-9]{3})   # Optional millisecond
Z                       # Z for 00:00
""", re.VERBOSE)

def flatten_config(config_dict, prefix="", suffix=False):
    ret = {}
    if prefix:
        pre = f"{prefix}_"
    else:
        pre = ""
    for key, val in config_dict.items():
        if isinstance(val, Mapping):
            nested = flatten_config(val, key, suffix)
            for nkey, nval in nested.items():
                full_key = f"{pre}{nkey}"
                assert full_key not in ret
                ret[full_key] = nval
        elif suffix and isinstance(val, list):
            for pos, item in enumerate(val):
                if isinstance(item, Mapping):
                    subkey = f"{key}_{pos}"
                    nested = flatten_config(item, subkey, suffix)
                    for nkey, nval in nested.items():
                        full_key = f"{pre}{nkey}"
                        assert full_key not in ret
                        ret[full_key] = nval
                else:
                    full_key = f"{pre}{key}_{pos}"
                    assert full_key not in ret
                    ret[full_key] = item
        else:
            full_key = f"{pre}{key}"
            assert full_key not in ret
            ret[full_key] = val
    return ret


def to_csv(pools, csv_file, full_csv_datetimes=False, csv_set=None):
    """
    Ouput worker pool data to a CSV file.

    pools - a list of worker pool info dictionaries
    csv_file - a file-like object
    """

    # Flatten pool configs
    headers = []
    header_set = set()
    flat_configs = []
    for pool in pools:
        flat_pool = flatten_config(pool)
        launch_configs = flat_pool.pop('config_launchConfigs', [])
        for config in launch_configs:
            flat_config = flat_pool.copy()
            flat_config |= flatten_config(config, "lc", True)
            flat_configs.append(flat_config)
            # Gather header rows
            for key in flat_config.keys():
                if key not in header_set:
                    header_set.add(key)
                    headers.append(key)

    # Pick a smaller set if requested
    if csv_set:
        columns = CSV_SET[csv_set]["columns"]
        counts = defaultdict(int)
        for flat_config in flat_configs:
            out_key = tuple(flat_config.get(key, '') for key in columns)
            counts[out_key] += 1
        output_flat_configs = []
        for row in sorted(counts.keys()):
            out = dict(zip(columns, row))
            out["launch_config_count"] = counts[row]
            output_flat_configs.append(out)
        out_headers = columns + ["launch_config_count"]
    else:
        out_headers = headers
        output_flat_configs = flat_configs

    # Output to CSV
    output = DictWriter(csv_file, fieldnames=out_headers)
    output.writeheader()
    date_keys = set(("created", "expires", "lastModified", "lastChecked"))
    for row_num, raw_pool in enumerate(output_flat_configs):
        row = {}
        for key, raw_value in raw_pool.items():
            # Convert datetime strings to timezone-naive datetimes w/o fractional seconds
            if key in date_keys:
                dt_match = RE_DATETIME.match(raw_value)
                if not dt_match:
                    logger.error(f"Failed to match datetime on row {row_num} for {key} with value {raw_value!r}")
                    assert dt_match
                year, month, day, hour, minute, second, millisecond = dt_match.groups()
                if full_csv_datetimes:
                    value = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), 1000 * int(millisecond or 0), timezone.utc)
                else:
                    value = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
            else:
                value = raw_value
            row[key] = value
        output.writerow(row)


def worker_pool_summary(pools):
    """Return a text summary of worker pool data."""

    key_set = set()

    for pool in pools:
        pool_id = pool.get('workerPoolId', '')
        provider_id = pool.get('providerId', '')
        capacity = int(pool.get('currentCapacity', 0))
        owner = pool.get('owner', '')
        config = pool.get('config', {})
        max_capacity = config.get('maxCapacity', '')
        min_capacity = config.get('minCapacity', '')
        launch_configs = config.get('launchConfigs', [])
        launch_configs_count = len(launch_configs)
        key = (pool_id, provider_id, capacity, min_capacity, max_capacity, owner, launch_configs_count)
        key_set.add(key)

    keys = sorted(key_set)

    def max_width(title, index, keys):
        return max(len(title), max(len(str(key[index])) for key in keys))

    titles = ('Pool ID', 'Provider ID', 'Capacity', 'Min Cap', 'Max Cap', 'Owner', 'Launch Configs')
    width = {
        title: max(len(title), max(len(str(key[index])) for key in keys))
        for index, title
        in enumerate(titles)
    }

    col = "  "
    output = [col.join(f"{title:<{width[title]}}" for title in titles)]
    for key in keys:
        pool_id, provider_id, capacity, min_capacity, max_capacity, owner, launch_configs = key
        output.append(
            f"{pool_id:<{width['Pool ID']}}{col}"
            f"{provider_id:<{width['Provider ID']}}{col}"
            f"{capacity:>{width['Capacity']}}{col}"
            f"{min_capacity:>{width['Min Cap']}}{col}"
            f"{max_capacity:>{width['Max Cap']}}{col}"
            f"{owner:<{width['Owner']}}{col}"
            f"{launch_configs:>{width['Launch Configs']}}"
        )

    output.extend(['', ''])
    output.append(f"Worker Pools: {len(pools)}")
    return "\n".join(output)

def get_parser():
    parser = argparse.ArgumentParser(
        description="Get all worker pools configurations")
    parser.add_argument(
        '--csv-file',
        help="Output worker pool data in CSV format")
    parser.add_argument(
        '--full-datetimes',
        action='store_true',
        help=("In CSV, retain microseconds and timezone in date/times,"
              " which may prevent them being parsed as dates."))
    set_helps = [f"{key}={val['description']}" for key, val in CSV_SET.items()]
    parser.add_argument(
        '--csv-set',
        help="Select a set of columns for the CSV (" + ", ".join(set_helps) + ")",
        choices=CSV_SET.keys()
    )
    parser.add_argument(
        '--json-file',
        help="Output worker pool data in JSON format")
    parser.add_argument(
        '--from-json-file',
        help="Get worker pool data from JSON file instead of API")
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        help="Print debugging information, repeat for more detail")
    return parser


if __name__ == "__main__":
    auth_options = taskcluster.optionsFromEnvironment()
    parser = get_parser()
    args = parser.parse_args()
    if not auth_options and not args.from_json_file:
        print("TASKCLUSTER_ROOT_URL not in environment, see README.md")
        sys.exit(1)
    if args.verbose and args.verbose >= 2:
        level = 'DEBUG'
    else:
        level = 'INFO'
    logging.basicConfig(level=level)
    retcode = main(
        auth_options,
        verbose=args.verbose,
        csv_file=args.csv_file,
        json_file=args.json_file,
        from_json_file=args.from_json_file,
        full_csv_datetimes=args.full_datetimes,
        csv_set=args.csv_set
    )
    sys.exit(retcode)
