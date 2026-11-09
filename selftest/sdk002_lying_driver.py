"""Self-test for CT-SDK-002: an SDK that reports a rejected configuration as accepted.
Pointed to by `sdk.python`, it must make CT-SDK-002 FAIL."""
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parent.parent / "setup" / "sdk_aqef_client.py"
_s = importlib.util.spec_from_file_location("real_sdk_driver", _p)
real = importlib.util.module_from_spec(_s)
_s.loader.exec_module(real)

LANGUAGE, VERSION, Unmapped, TransportError = real.LANGUAGE, real.VERSION, real.Unmapped, real.TransportError


def call(base_url, token, method, path, **kw):
    status, raw, op = real.call(base_url, token, method, path, **kw)
    if method == "POST" and path == "/projects" and 400 <= status < 500:
        return 201, b"{}", op      # the defect: an API error turned into success
    return status, raw, op
