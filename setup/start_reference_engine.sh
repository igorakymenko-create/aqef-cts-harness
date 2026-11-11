#!/bin/sh
# Start aqef-reference-engine with the CTS model identifiers mapped to this harness's
# scripted services, then create the CTS Principals. Run it from the engine's checkout:
#   sh /path/to/aqef-cts-harness/setup/start_reference_engine.sh
HERE=$(cd "$(dirname "$0")" && pwd)
J=http://127.0.0.1:9100/judge
M="{\"cts-scripted-subject@1\":\"http://127.0.0.1:9100/subject\",\"cts-scripted-judge@1\":\"$J\",\"cts-scripted-judge@2\":\"$J\",\"cts-scripted-judge-a@1\":\"$J\",\"cts-scripted-judge-b@1\":\"$J\",\"cts-scripted-judge-c@1\":\"$J\",\"cts-reference-judge@1\":\"$J\",\"cts-scripted-generator@1\":\"http://127.0.0.1:9100/generator\"}"
# Section 24: the capture source of the Production Replay fixtures (docs/DATASETS.md)
C="{\"cts-capture\":\"http://127.0.0.1:9100/capture\"}"
# Section 23: the tool executor for sandbox and real calls, and the subject whose access
# the harness controls (the engine's docs/ACTION-BOUNDARY.md)
X="{\"sandbox\":\"http://127.0.0.1:9100/executor\",\"real\":\"http://127.0.0.1:9100/executor\"}"
S="[\"cts-scripted-subject@1\"]"
rm -f /tmp/aqef-cts.db
AQEF_PROVIDER_URLS="$M" AQEF_CAPTURE_URLS="$C" AQEF_TOOL_EXECUTOR_URLS="$X" AQEF_CONTROLLED_SUBJECTS="$S" AQEF_DB_PATH=/tmp/aqef-cts.db python3 -m uvicorn engine.main:app --host 127.0.0.1 --port 8000 > /tmp/aqef-engine.log 2>&1 &
for i in $(seq 1 20); do curl -s -o /dev/null http://127.0.0.1:8000/healthz && break; sleep 1; done
python3 "$HERE/bootstrap_reference_engine.py" http://127.0.0.1:8000 admin-token
