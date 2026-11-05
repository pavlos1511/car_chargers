
#!/bin/
bash
set -e
echo "== sessions csv =="
../se2515 sessions --id 1 --from 20251101 --to 20251130
echo
echo "== sessions json =="
../se2515 sessions --id 1 --from 20251101 --to 20251130 --format json
