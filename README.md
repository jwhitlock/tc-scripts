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

## worker_pool_stats.py - Worker Pool Stats

This script can be used to:

* Summarize the workers and capacity in a pool by group and status (default)
* Export detailed data in CSV (``--csv-file CSV_FILE``) and JSON (``--json-file JSON FILE``) formats
* Use previously exported JSON data instead of calling the API (useful for rapid script development)

Output of ``./worker_pool_stats.py --help``:

```
usage: worker_pool_stats.py [-h] [--csv-file CSV_FILE] [--full-datetimes] [--json-file JSON_FILE] [--from-json-file FROM_JSON_FILE] [-v] [pool_id]

Examine workers in a worker pool, print a summary.

positional arguments:
  pool_id               Pool identifier, like 'gecko-t/win10-64-2004'

optional arguments:
  -h, --help            show this help message and exit
  --csv-file CSV_FILE   Output worker data in CSV format
  --full-datetimes      In CSV, retain microseconds and timezone in date/times, which may prevent them being parsed as dates.
  --json-file JSON_FILE
                        Output worker data in JSON format
  --from-json-file FROM_JSON_FILE
                        Get worker data from JSON file instead of API
  -v, --verbose         Print debugging information, repeat for more detail
```

## worker_pool_type.py - Detailed worker pool configuration

This script can be used to:

* Output the worker configurations as a text table
* Output the detailed worker configurations as a CSV

Output of ``./worker_pool_type.py --help``:

```
usage: worker_pool_types.py [-h] [--csv-file CSV_FILE] [--full-datetimes]
                            [--csv-set {images,aws-images,gcp-images,azure-images}]
                            [--json-file JSON_FILE] [--from-json-file FROM_JSON_FILE]
                            [--skip-summary] [-v]

Get all worker pools configurations

optional arguments:
  -h, --help            show this help message and exit
  --csv-file CSV_FILE   Output worker pool data in CSV format
  --full-datetimes      In CSV, retain microseconds and timezone in date/times, which may
                        prevent them being parsed as dates.
  --csv-set {images,aws-images,gcp-images,azure-images}
                        Select a set of columns for the CSV (images=AWS/GCP/Azure images by
                        pool, aws-images=Unique AWS AMIs, gcp-images=Unique GCP images, azure-
                        images=Unique Azure images)
  --json-file JSON_FILE
                        Output worker pool data in JSON format
  --from-json-file FROM_JSON_FILE
                        Get worker pool data from JSON file instead of API
  --skip-summary        Skip summary
  -v, --verbose         Print debugging information, repeat for more detail
```

## get_worker_pool_types.sh

Use ``worker_pool_type.py`` to generate a set of JSON and CSVs:

```
./get_worker_pool_types.sh
ls wpt
```
