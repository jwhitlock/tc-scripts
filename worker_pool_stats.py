#!/usr/bin/env python3

from collections import defaultdict
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
        pool_id,
        verbose=False,
        json_file=None,
        from_json_file=None,
        csv_file=None,
        full_csv_datetimes=False
    ):
    """
    Collect and summarize worker data for a pool

    auth_options - Options, such as output of taskcluster.optionsFromEnvironment()
    pool_id - The pool ID, such as 'gecko-t/win10-64-2004'
    verbose - True to log progress messages
    json_file - Path to a file to store worker data as JSON
    from_json_file - Load worker data from a JSON file instead of API
    csv_file - Path to a file to store worker data as a CSV
    full_csv_datetimes - If True, keep microseconds and timezones on dates.
      This may prevent them from being interpreted as dates by spreadsheet
      programs.
    """
    if from_json_file:
        with open(from_json_file, 'r') as the_file:
            workers = json.load(the_file)
        if verbose:
            logger.info("Loaded {len(workers)} workers from {from_json_file}.")
    else:
        worker_manager = taskcluster.WorkerManager(auth_options)
        worker_manager.ping()
        if verbose:
            logger.info("Worker Manager is available.")

        pool = worker_manager.workerPool(pool_id)
        if verbose:
            logger.info(f"Pool {pool['workerPoolId']} found.")

        workers = get_pool_workers(worker_manager, pool_id, verbose=verbose)

    if csv_file:
        if verbose:
            logger.info(f"Writing worker data to {csv_file}...")
        with open(csv_file, 'w', newline='') as the_file:
            to_csv(workers, the_file, full_csv_datetimes)
        if verbose:
            logger.info(f"Done writing {csv_file}.")

    if json_file:
        with open(json_file, 'w') as the_file:
            json.dump(workers, the_file)
        if verbose:
            logger.info(f"Wrote JSON worker data to {json_file}.")

    print(worker_summary(workers))

    return 0


def get_pool_workers(worker_manager, pool_id, verbose=False):
    """Get the workers in a pool, following pagination"""

    page = worker_manager.listWorkersForWorkerPool(pool_id)
    page_count = 1
    token = page.get('continuationToken', None)
    workers = page['workers']
    if verbose:
        logger.info(f"Getting workers, page 1, {len(workers)} workers...")
    while token:
        page = worker_manager.listWorkersForWorkerPool(
            pool_id, query={'continuationToken': token})
        token = page.get('continuationToken', None)
        workers.extend(page.get('workers', []))
        page_count += 1
        if verbose:
            logger.info(f"Getting workers, page {page_count}, {len(workers)} workers...")
    if verbose:
        logger.info(f"Found {len(workers)} workers.")
    return workers

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


def to_csv(workers, csv_file, full_csv_datetimes=False):
    """
    Ouput worker data to a CSV file.

    workers - a list of worker info dictionaries
    csv_file - a file-like object
    """

    # Gather header rows
    headers = []
    header_set = set()
    for worker in workers:
        for key in worker.keys():
            if key not in header_set:
                header_set.add(key)
                headers.append(key)

    # Output to CSV
    output = DictWriter(csv_file, fieldnames=headers)
    output.writeheader()
    date_keys = set(("created", "expires", "lastModified", "lastChecked"))
    for row_num, raw_worker in enumerate(workers):
        row = {}
        for key, raw_value in raw_worker.items():
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


def worker_summary(workers):
    """Return a text summary of worker data."""

    key_set = set()
    key_worker_counts = defaultdict(int)
    key_capacity_counts = defaultdict(int)
    state_worker_counts = defaultdict(int)
    state_capacity_counts = defaultdict(int)
    state_order = ['requested', 'running', 'stopping', 'stopped']
    known_states = set(state_order)

    for worker in workers:
        pool_id = worker.get('workerPoolId', '')
        group = worker.get('workerGroup', '')
        provider_id = worker.get('providerId', '')
        state = worker.get('state', '')
        capacity = int(worker.get('capacity', 1))
        key = (pool_id, group, provider_id, state)

        key_set.add(key)
        key_worker_counts[key] += 1
        key_capacity_counts[key] += capacity
        state_worker_counts[state] += 1
        state_capacity_counts[state] += 1

        if state not in known_states:
            state_order.append(state)
            known_states.add(state)

    keys = sorted(key_set, key=lambda k: (k[0], k[1], k[2], state_order.index(k[3])))
    pool_id_len = max(len('Pool ID'), max(len(key[0]) for key in keys))
    group_len = max(len('Group ID'), max(len(key[1]) for key in keys))
    provider_len = max(len('Provider ID'), max(len(key[2]) for key in keys))
    state_len = max(len(state) for state in known_states)
    workers_len = len('Workers')
    capacity_len = len('Capacity')
    col = "  "
    output = [
        f"{'Pool ID':<{pool_id_len}}{col}"
        f"{'Group ID':<{group_len}}{col}"
        f"{'Provider ID':<{provider_len}}{col}"
        f"{'State':<{state_len}}{col}"
        f"{'Workers':<{workers_len}}{col}"
        f"{'Capacity':<{capacity_len}}"
    ]
    for key in keys:
        pool_id, group_id, provider_id, state = key
        workers = key_worker_counts[key]
        capacity = key_capacity_counts[key]
        output.append(
            f"{pool_id:<{pool_id_len}}{col}"
            f"{group_id:<{group_len}}{col}"
            f"{provider_id:<{provider_len}}{col}"
            f"{state:<{state_len}}{col}"
            f"{workers:<{workers_len}}{col}"
            f"{capacity:<{capacity_len}}"
        )

    output.extend(['', ''])
    output.append(
        f"{'State':<{state_len}}{col}"
        f"{'Workers':<{workers_len}}{col}"
        f"{'Capacity':<{capacity_len}}"
    )
    for state in state_order:
        workers = state_worker_counts[state]
        capacity = state_capacity_counts[state]
        output.append(
            f"{state:<{state_len}}{col}"
            f"{workers:<{workers_len}}{col}"
            f"{capacity:<{capacity_len}}"
        )

    return "\n".join(output)

def get_parser():
    parser = argparse.ArgumentParser(
        description="Examine workers in a worker pool, print a summary.")
    parser.add_argument(
        'pool_id',
        nargs='?',
        help="Pool identifier, like 'gecko-t/win10-64-2004'")
    parser.add_argument(
        '--csv-file',
        help="Output worker data in CSV format")
    parser.add_argument(
        '--full-datetimes',
        action='store_true',
        help=("In CSV, retain microseconds and timezone in date/times,"
              " which may prevent them being parsed as dates."))
    parser.add_argument(
        '--json-file',
        help="Output worker data in JSON format")
    parser.add_argument(
        '--from-json-file',
        help="Get worker data from JSON file instead of API")
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
    if not args.pool_id and not args.from_json_file:
        parser.error("The following arguments are required: pool_id")
    if args.verbose and args.verbose >= 2:
        level = 'DEBUG'
    else:
        level = 'INFO'
    logging.basicConfig(level=level)
    retcode = main(
        auth_options,
        args.pool_id,
        verbose=args.verbose,
        csv_file=args.csv_file,
        json_file=args.json_file,
        from_json_file=args.from_json_file,
        full_csv_datetimes=args.full_datetimes
    )
    sys.exit(retcode)
