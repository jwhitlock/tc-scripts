#!/bin/bash

function get_data {
    TARGET=$1
    if [ "$TARGET" == "firefox-ci-tc" ]; then
        export TASKCLUSTER_ROOT_URL=https://firefox-ci-tc.services.mozilla.com
    elif [ "$TARGET" == "community-tc" ]; then
        export TASKCLUSTER_ROOT_URL=https://community-tc.services.mozilla.com
    else
        echo "Unknown target $TARGET"
        exit 1
    fi

    echo "*** Getting data for $TARGET"

    JSON=wpt/$TARGET.json
    get_json $JSON
    get_csv "Pool details" $JSON wpt/$TARGET.details.csv
    get_csv "Image details" $JSON wpt/$TARGET.all_images.csv images
    get_csv "AWS images (AMIs)" $JSON wpt/$TARGET.aws.csv aws-images
    get_csv "GCP images" $JSON wpt/$TARGET.gcp.csv gcp-images
    get_csv "Azure images" $JSON wpt/$TARGET.azure.csv azure-images
}

function get_json {
    JSON=$1
    ./worker_pool_types.py --skip-summary --json-file wpt/raw.json
    if type jq > /dev/null; then
      cat wpt/raw.json | jq > $JSON
      rm wpt/raw.json
    else
      mv wpt/raw.json $JSON
    fi
    echo "* Worker pool JSON written to $JSON"
}

function get_csv {
    DATA=$1
    JSON=$2
    CSV=$3
    CSV_SET=$4

    if [ "$CSV_SET" == "" ]; then
        ./worker_pool_types.py --skip-summary --from-json-file $JSON \
            --csv-file $CSV
    else
        ./worker_pool_types.py --skip-summary --from-json-file $JSON \
            --csv-set $CSV_SET --csv-file $CSV
    fi
    echo "* $DATA written to $CSV"
}

mkdir -p wpt
get_data "firefox-ci-tc"
get_data "community-tc"
