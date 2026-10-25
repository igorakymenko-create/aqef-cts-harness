"""Evidence store and manifest (Harness Contract §12): every object is stored as the
exact bytes written, with its SHA-256; the manifest is canonicalized with RFC 8785."""
import datetime
import hashlib
import json
import pathlib


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceStore:
    def __init__(self, root, run_id, validator):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.v = validator
        self.entries = []
        self._n = {}

    def add(self, case_id, kind, obj):
        """Store `obj` as JSON; return its evidence:// reference."""
        n = self._n.get(case_id, 0) + 1
        self._n[case_id] = n
        eid = f"{case_id or 'run'}-{n:03d}"
        name = f"{eid}.json"
        data = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False).encode("utf-8")
        (self.root / name).write_bytes(data)
        e = {"evidence_id": eid, "kind": kind, "raw_ref": f"evidence://{name}",
             "raw_sha256": hashlib.sha256(data).hexdigest(), "raw_size": len(data),
             "redaction_policy": "no-secrets-recorded", "collected_at": now()}
        if case_id:
            e["case_id"] = case_id
        self.entries.append(e)
        return e["raw_ref"]

    def manifest(self):
        m = {"schema_version": "0.8", "run_id": self.run_id, "created_at": now(),
             "canonicalization": "RFC8785", "entries": self.entries}
        m["manifest_sha256"] = self.v.sha256_hex(self.v.jcs(m).encode("utf-8"))
        return m
