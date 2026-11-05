#!/bin/bash
set -e

CLI="python3 ../se2515"
POINT_ID=100

S1="2026-02-01 10:00"
E1="2026-02-01 11:00"

S2="2026-02-02 12:00"
E2="2026-02-02 14:00"

D1="20260201"
D2="20260202"

pause() {
  read -p "Press Enter to continue..."
}

echo "===================================="
echo " EV Charging CLI Demo Flow"
echo "===================================="

echo
echo "1. healthcheck"
$CLI healthcheck
pause

echo
echo "2. resetpoints"
$CLI resetpoints
pause

echo
echo "3. addpoints"
$CLI addpoints --source sample_points.csv
pause

echo
echo "4. healthcheck"
$CLI healthcheck
pause

echo
echo "5. points --status available"
$CLI points --status available --format json
pause

echo
echo "6. points --status charging"
$CLI points --status charging --format json
pause

echo
echo "7. points --status offline"
$CLI points --status offline --format json
pause

echo
echo "8. point --id X"
$CLI point --id $POINT_ID
pause

echo
echo "9. reserve --id X"
$CLI reserve --id $POINT_ID
pause

echo
echo "10. points --status reserved"
$CLI points --status reserved --format json
pause

echo
echo "11. point --id X"
$CLI point --id $POINT_ID
pause

echo
echo "12. updpoint --id X --status available"
$CLI updpoint --id $POINT_ID --status available
pause

echo
echo "13. point --id X"
$CLI point --id $POINT_ID
pause

echo
echo "14. reserve --id X"
$CLI reserve --id $POINT_ID
pause

echo
echo "15. points --status reserved"
$CLI points --status reserved --format json
pause

echo
echo "16. newsession (Session 1)"
$CLI newsession \
  --id $POINT_ID \
  --starttime "$S1" \
  --endtime "$E1" \
  --startsoc 10 \
  --endsoc 30 \
  --totalkwh 15 \
  --kwhprice 0.5 \
  --amount 7.5
pause

echo
echo "17. pointstatus --id X --from S1 --to E1"
$CLI pointstatus --id $POINT_ID --from $D1 --to $D1 --format json
pause

echo
echo "18. point --id X"
$CLI point --id $POINT_ID
pause

echo
echo "19. newsession (Session 2)"
$CLI newsession \
  --id $POINT_ID \
  --starttime "$S2" \
  --endtime "$E2" \
  --startsoc 50 \
  --endsoc 80 \
  --totalkwh 20 \
  --kwhprice 0.6 \
  --amount 12
pause

echo
echo "20. sessions --id X --from S1 --to E2"
$CLI sessions --id $POINT_ID --from $D1 --to $D2 --format json
pause

echo
echo "21. pointstatus --id X --from S1 --to E2"
$CLI pointstatus --id $POINT_ID --from $D1 --to $D2 --format json
pause

echo
echo "===================================="
echo " Demo Completed Successfully"
echo "===================================="

