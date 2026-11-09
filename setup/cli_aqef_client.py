"""CLI driver for CT-SDK-001: the `aqef` command of aqef-reference-engine's `aqef-client`
(docs/CLI.md). Everything specific to this CLI lives here; the test itself is generic.

Each function returns the argument vector for one documented command. The harness runs
it with AQEF_URL set to its recording proxy and AQEF_TOKEN set to the Principal's token,
so no token appears in an argument vector."""
import os
import shutil
import sys

# Override with AQEF_CLI, e.g. AQEF_CLI=/path/to/venv/bin/aqef
EXE = os.environ.get("AQEF_CLI") or shutil.which("aqef") or "aqef"

def load(file):
    return [EXE, "--json", "project", "load", str(file)]


def execute(project, suite, environment):
    return [EXE, "--json", "execution", "run", "--project", project,
            "--suite", suite, "--environment", environment, "--wait"]


def check_gates(project, file):
    return [EXE, "--json", "gates", "check", "--project", project, str(file)]


def help_commands():
    """Argument vectors whose output lists every documented command: the top-level help,
    then the help of each command group it names."""
    import re
    import subprocess
    top = subprocess.run([EXE, "--help"], capture_output=True, text=True, timeout=60).stdout
    m = re.search(r"{([^}]+)}", top)
    groups = m.group(1).split(",") if m else []
    return [[EXE, "--help"]] + [[EXE, g, "--help"] for g in groups]


if __name__ == "__main__":
    print(EXE, file=sys.stderr)
