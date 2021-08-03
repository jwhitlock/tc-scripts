# Taskcluster Scripts

These are scripts that talk to the Taskcluster API.

## Setup

Download and install the [taskcluster-cli](https://github.com/taskcluster/taskcluster/tree/main/clients/client-shell#readme), so you can run:

```bash
export TASKCLUSTER_ROOT_URL=https://firefox-ci-tc.services.mozilla.com/
taskcluster signin
```

This will take you to Taskcluster to create a token, which you then set in
environment variables:

```bash
export TASKCLUSTER_CLIENT_ID='the_client_id'
export TASKCLUSTER_ACCESS_TOKEN='the_access_token'
export TASKCLUSTER_ROOT_URL='https://firefox-ci-tc.services.mozilla.com/'
```

A virtual environment is recommended, such as:

```bash
python -m venv .venv
```

and then an install:

```bash
pip install -r requirements.txt
```

## worker-pool-stats.py - Worker Pool Stats

Output of ``./worker-pool-stats.py``:

```
usage: worker-pool-stats.py [-h] [--csv-file CSV_FILE] [--json-file JSON_FILE] [--from-json-file FROM_JSON_FILE]
                            [-v]
                            pool_id

Examine workers in a worker pool, print a summary.

positional arguments:
  pool_id               Pool identifier, like 'gecko-t/win10-64-2004'

optional arguments:
  -h, --help            show this help message and exit
  --csv-file CSV_FILE   Output worker data in CSV format
  --json-file JSON_FILE
                        Output worker data in JSON format
  --from-json-file FROM_JSON_FILE
                        Get worker data from JSON file instead of API
  -v, --verbose         Print debugging information, repeat for more detail
```
