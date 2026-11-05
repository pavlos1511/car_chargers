#!/bin/bash
set -e
echo "===================================="
echo " Running ALL CLI automated tests"
echo "===================================="
echo
./test_healthcheck.sh
./test_resetpoints.sh
./test_addpoints.sh
./test_points.sh
./test_point.sh
./test_reserve.sh
./test_updpoint.sh
./test_newsession.sh
./test_sessions.sh
./test_pointstatus.sh
echo
echo " All CLI tests completed successfully"
