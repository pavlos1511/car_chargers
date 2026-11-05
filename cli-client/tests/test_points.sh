#!/bin/bash
set -e
echo "== points (csv default) =="
../se2515 points
echo
echo "== points (json) =="
../se2515 points --format json
