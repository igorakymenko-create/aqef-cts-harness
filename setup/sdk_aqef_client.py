"""Python SDK driver for CT-SDK-002: aqef-reference-engine's `aqef_client` (docs/SDK.md).

The harness's tests speak Appendix C: a method, a path, a body. This driver carries out
each such request through the SDK's *named* operation for that route, never through its
low-level `request()`, so that what is tested is the SDK surface a user calls. The route
of each named operation is read from its docstring, which docs/SDK.md documents as
repeating the verb and path ("POST /projects/{project}/gates/check.")."""
import inspect
import re
import urllib.parse

import aqef_client
from aqef_client import APIError, Client, TransportError

LANGUAGE = "python"
VERSION = getattr(aqef_client, "__version__", "unknown")

_ROUTE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH) (/\S*?)\.?$")
_HEADER = {"X-Approved-By": "x_approved_by", "X-External-Review-Ref": "x_external_review_ref"}


def _routes():
    out = []
    for name, fn in inspect.getmembers(Client, inspect.isfunction):
        doc = (fn.__doc__ or "").strip().splitlines()
        m = _ROUTE.match(doc[0]) if doc else None
        if not m or name == "request":
            continue
        method, template = m.groups()
        names = re.findall(r"{(\w+)}", template)
        rx = re.compile("^" + re.sub(r"{\w+}", r"([^/]+)", template) + "$")
        out.append((method, rx, names, name, inspect.signature(fn)))
    # Literal segments win over parameters ("/gates/check" before "/gates/{gate}").
    out.sort(key=lambda r: r[1].pattern.count("([^/]+)"))
    return out


ROUTES = _routes()


class Unmapped(Exception):
    """No named SDK operation serves this route."""


def call(base_url, token, method, path, body=None, headers=None, timeout=30.0):
    """Carry out one request through the SDK. Returns (status, raw_bytes, operation)."""
    split = urllib.parse.urlsplit(path)
    query = dict(urllib.parse.parse_qsl(split.query))
    for m, rx, names, op, sig in ROUTES:
        hit = rx.match(split.path) if m == method else None
        if not hit:
            continue
        kwargs = {n: urllib.parse.unquote(v) for n, v in zip(names, hit.groups())}
        for k, v in query.items():
            if k not in sig.parameters:
                raise Unmapped(f"{op} has no query parameter {k}")
            kwargs[k] = {"true": True, "false": False}.get(v, v)
        for h, v in (headers or {}).items():
            kw = _HEADER.get(h)
            if kw is None or kw not in sig.parameters:
                raise Unmapped(f"{op} takes no header {h}")
            kwargs[kw] = v
        if "body" in sig.parameters:
            kwargs["body"] = body
        elif body is not None:
            raise Unmapped(f"{op} takes no body")
        with Client(base_url, token, timeout=timeout) as api:
            try:
                r = getattr(api, op)(**kwargs)
                return r.status_code, r.content, op
            except APIError as e:
                return e.status_code, e.body, op
    raise Unmapped(f"no named SDK operation for {method} {split.path}")


__all__ = ["LANGUAGE", "VERSION", "call", "Unmapped", "TransportError"]
