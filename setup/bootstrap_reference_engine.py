"""Create the CTS Principals (CTS 14.1) in aqef-reference-engine, through its own
documented API (its docs/API.md): roles with POST /roles, Principals with POST
/principals, as the bootstrap admin. Specific to that engine; another engine needs its
own setup script. Prints the `tokens:` block for harness.yaml.

    python setup/bootstrap_reference_engine.py http://127.0.0.1:8000 admin-token
"""
import json
import sys
import urllib.error
import urllib.request

# CTS 14.1. The loader (P-APPROVER) also gets project_create, dataset_create and
# project_edit, which CTS 14.1 gives to no Principal although loading and replacing a
# configuration need them.
ROLES = {
    "cts-release": ["read", "execute", "release_decide"],
    "cts-approver": ["read", "execute", "contract_define", "gate_override", "baseline_approve",
                     "environment_edit", "scenario_edit", "environment_delete",
                     "project_create", "dataset_create", "project_edit",
                     "scenario_create", "scenario_delete"],   # CT-CFG-029
    "cts-noperm": ["read", "execute"],
    "cts-editor": ["read", "project_edit", "scenario_edit"],
    "cts-reviewer": ["read", "review"],
    "reviewer": [],
    "cts-admin": ["read", "project_delete", "audit_read", "role_admin"],   # role_admin: CT-REL-019, 033
    "release_manager": ["read", "execute"],                              # CTS CT-REL-032
    "observer": ["read", "execute", "release_decide"],                   # CTS CT-REL-032
    "qa": [],
    "lead": [],
    "cts-invalidate": ["read", "seeded_control_invalidate"],
    "cts-sa": ["read", "execute", "release_decide", "gate_override", "baseline_approve",
               "contract_define"],
}
PRINCIPALS = [
    ("P-RELEASE", "person", ["cts-release"], None),
    ("P-APPROVER", "person", ["cts-approver"], None),
    ("P-NOPERM", "person", ["cts-noperm"], None),
    ("P-EDITOR", "person", ["cts-editor"], None),
    ("P-REVIEWER", "person", ["cts-reviewer", "reviewer"], None),
    ("P-ADMIN", "person", ["cts-admin"], None),
    ("SA-CI", "service_account", ["cts-sa"], "P-RELEASE"),
    ("SA-REVIEW", "service_account", ["cts-reviewer"], "P-REVIEWER"),   # CTS 16.1
    ("P-REVIEWER-2", "person", ["cts-reviewer", "qa"], None),            # CTS 20
    ("P-LEAD", "person", ["cts-reviewer", "lead"], None),                # CTS CT-HRV-005
    ("P-INVALIDATE", "person", ["cts-invalidate"], None),                # CTS CT-SCT-007
    ("P-ROLE-A", "person", ["release_manager"], None),                   # CTS CT-REL-032
    ("P-ROLE-B", "person", ["observer"], None),                          # CTS CT-REL-032
]


def post(base, admin, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {admin}"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return 409
        raise SystemExit(f"{path}: {e.code} {e.read().decode()}")


def main(base, admin):
    base = base.rstrip("/")
    for name, perms in ROLES.items():
        post(base, admin, "/roles", {"name": name, "permissions": perms})
    tokens = {}
    for pid, kind, roles, owner in PRINCIPALS:
        tok = f"cts-{pid.lower()}"
        body = {"id": pid, "kind": kind, "name": pid, "roles": roles, "token": tok}
        if owner:
            body["owner_person_id"] = owner
        post(base, admin, "/principals", body)
        tokens[pid] = tok
    print("tokens:")
    for k, v in tokens.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
