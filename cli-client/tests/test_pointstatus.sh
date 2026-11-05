#!/bin/bash
set -e
echo "== pointstatus csv =="
../se2515 pointstatus --id 1 --from 20251101 --to 20251130
echo
echo "== pointstatus json =="
../se2515 pointstatus --id 1 --from 20251101 --to 20251130 --format json
