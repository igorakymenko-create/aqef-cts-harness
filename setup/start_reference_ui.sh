#!/bin/sh
# Start aqef-reference-ui for CT-RUI-001, from that UI's checkout:
#   sh /path/to/aqef-cts-harness/setup/start_reference_ui.sh
# It starts the engine the UI vendors (vendor/engine), with the CTS model identifiers
# mapped to this harness's scripted services, creates the CTS Principals, then starts
# the UI's own Person (its startup step), then the UI's workspace service on an empty
# workspace and the UI itself on :3000.
# Nothing of the UI's own sample is loaded. Stop everything with: kill $(cat $RUN/pids)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
RUN=${RUN:-$(mktemp -d /tmp/aqef-rui.XXXXXX)}
TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(24))")
J=http://127.0.0.1:9100/judge
M="{\"cts-scripted-subject@1\":\"http://127.0.0.1:9100/subject\",\"cts-scripted-judge@1\":\"$J\",\"cts-scripted-judge@2\":\"$J\",\"cts-scripted-judge-a@1\":\"$J\",\"cts-scripted-judge-b@1\":\"$J\",\"cts-scripted-judge-c@1\":\"$J\",\"cts-reference-judge@1\":\"$J\"}"
mkdir -p "$RUN/workspace"
printf '# Replaced by the harness before use.\nplaceholder: true\n' > "$RUN/workspace/project.yaml"
: > "$RUN/pids"
AQEF_ADMIN_TOKEN=$TOKEN AQEF_PROVIDER_URLS="$M" AQEF_DB_PATH="$RUN/engine.db" PYTHONPATH=vendor/engine \
  python3 -m uvicorn engine.main:app --host 127.0.0.1 --port 8000 > "$RUN/engine.log" 2>&1 &
echo $! >> "$RUN/pids"
for i in $(seq 1 40); do curl -s -o /dev/null -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/healthz && break; sleep 0.5; done
python3 "$HERE/bootstrap_reference_engine.py" http://127.0.0.1:8000 "$TOKEN" > "$RUN/tokens.txt"
# The UI acts as its own Person, created by the UI's own startup step (scripts/run_engine.py).
python3 -c "import sys; sys.path.insert(0, '.'); from scripts.run_engine import bootstrap_person; bootstrap_person('http://127.0.0.1:8000', sys.argv[1])" "$TOKEN"
python3 -m workspace_service.server --root "$RUN/workspace" > "$RUN/workspace.log" 2>&1 &
echo $! >> "$RUN/pids"
AQEF_ADMIN_TOKEN=$TOKEN npm run dev > "$RUN/ui.log" 2>&1 &
echo $! >> "$RUN/pids"
for i in $(seq 1 60); do curl -s -o /dev/null http://127.0.0.1:3000/ && break; sleep 0.5; done
echo "RUN=$RUN"
