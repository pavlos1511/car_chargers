#!/bin/bash
set -e
echo "== reserve default (30 min) =="
../se2515 reserve --id 1
echo
echo "== reserve explicit minutes =="
../se2515 reserve --id 2 --minutes 45
