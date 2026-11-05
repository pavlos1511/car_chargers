#!/bin/bash
set -e
echo "== newsession =="
../se2515 newsession \
  --id 1 \
  --starttime "2025-11-10 19:00" \
  --endtime "2025-11-10 20:30" \
  --startsoc 20 \
  --endsoc 80 \
  --totalkwh 15.5 \
  --kwhprice 0.50 \
  --amount 7.75
