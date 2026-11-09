"""Self-test for CT-SDK-001: a CLI whose `execution run` answers locally, without the REST
call. Pointed to by `cli.driver`, it must make CT-SDK-001 FAIL."""
import importlib.util
import json
import pathlib
import sys

_p = pathlib.Path(__file__).resolve().parent.parent / "setup" / "cli_aqef_client.py"
_s = importlib.util.spec_from_file_location("real_cli_driver", _p)
real = importlib.util.module_from_spec(_s)
_s.loader.exec_module(real)

load, check_gates, help_commands = real.load, real.check_gates, real.help_commands


def execute(project, suite, environment):
    out = json.dumps({"execution_batch_id": "local-batch", "executions": []})
    return [sys.executable, "-c", f"print({out!r})"]   # the defect: no REST call
