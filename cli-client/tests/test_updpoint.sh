#!/bin/bash
set -e
echo "== updpoint status =="
../se2515 updpoint --id 1 --status available
echo
echo "== updpoint price =="
../se2515 updpoint --id 1 --price 0.55
echo
echo "== updpoint status + price =="
../se2515 updpoint --id 2 --status available --price 0.60
