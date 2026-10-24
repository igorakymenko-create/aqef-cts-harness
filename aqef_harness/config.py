"""Run configuration: where the engine is, how to authenticate as each CTS Principal,
and where the AQEF repository (CTS, schemas, validator) is checked out."""
import pathlib
import sys
from dataclasses import dataclass, field

import yaml


@dataclass
class Config:
    aqef_repo: pathlib.Path
    base_url: str
    tokens: dict
    sut_name: str
    sut_version: str
    adapter_id: str = "aqef-rest-adapter"
    capabilities_claimed: list = field(default_factory=list)
    conformance_statement: pathlib.Path | None = None
    config_format: str = "json"          # body of POST /projects: json or yaml
    wrap_project: bool = False           # body is {"project": {...}} instead of {...}
    timeout_s: float = 30.0
    loader: str = "P-APPROVER"           # Principal who loads configurations (CTS 14.1)
    delete_query: str = ""               # query that requests retention on DELETE (Appendix C §C.8)
    scripted_port: int = 9100            # where the scripted subject and Judge listen
    engine_slices_done: int = 6          # parts of a test beyond this stage are NOT_RUN
    conversation_form: str = "messages"  # fixed Evidence form the engine stores: messages or turns
    team_binding: str = "unknown"
    manual_reviews: pathlib.Path | None = None   # CTS 1.8 review records (Harness Contract §13)        # from the Conformance Statement: none, or how it binds (CT-REL-039)

    @property
    def cts(self):
        return self.aqef_repo / "conformance-tests"

    def validator(self):
        """The validator module of the AQEF repository, which also holds RFC 8785 and
        the CTS inventory reader."""
        tools = str(self.cts / "harness" / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import validate  # noqa: E402
        return validate


def load(path):
    path = pathlib.Path(path)
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent
    def rel(p):
        return (base / p).resolve() if p else None
    return Config(
        aqef_repo=rel(d["aqef_repo"]),
        base_url=d["base_url"].rstrip("/"),
        tokens=d.get("tokens", {}),
        sut_name=d["sut"]["name"],
        sut_version=str(d["sut"]["version"]),
        adapter_id=d.get("adapter_id", "aqef-rest-adapter"),
        capabilities_claimed=d.get("capabilities_claimed", []),
        conformance_statement=rel(d.get("conformance_statement")),
        config_format=d.get("config_format", "json"),
        wrap_project=bool(d.get("wrap_project", False)),
        timeout_s=float(d.get("timeout_s", 30)),
        loader=d.get("loader", "P-APPROVER"),
        delete_query=d.get("delete_query", ""),
        scripted_port=int(d.get("scripted_port", 9100)),
        engine_slices_done=int(d.get("engine_slices_done", 6)),
        conversation_form=d.get("conversation_form", "messages"),
        team_binding=d.get("team_binding", "unknown"),
        manual_reviews=rel(d.get("manual_reviews")),
    )
