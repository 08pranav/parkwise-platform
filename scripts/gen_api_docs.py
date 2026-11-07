#!/usr/bin/env python3
"""Generate docs/API_DOCUMENTATION.md from docs/openapi.yaml.

Refresh the schema first:  cd backend && python manage.py spectacular --file ../docs/openapi.yaml
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
schema = yaml.safe_load((ROOT / "docs/openapi.yaml").read_text())

GROUPS = {
    "auth": "Accounts and authentication",
    "societies": "Societies, slots and search",
    "bookings": "Bookings",
    "payments": "Payments and webhooks",
    "qr": "Gate scanning (QR)",
    "penalties": "Penalties",
    "admin": "Admin, refunds and demo tools",
}


def group_of(path):
    parts = path.strip("/").split("/")
    return parts[2] if len(parts) > 2 and parts[1] == "v1" else "other"


rows = {}
for path, item in sorted(schema["paths"].items()):
    for method in ("get", "post", "put", "patch", "delete"):
        op = item.get(method)
        if not op:
            continue
        public = op.get("security") == [{}] or "security" in op and {} in op["security"]
        summary = (op.get("summary") or op.get("operationId") or "").replace("|", "\\|")
        rows.setdefault(group_of(path), []).append((method.upper(), path, summary, public))

total = sum(len(v) for v in rows.values())
lines = [
    "# API reference",
    "",
    f"Generated from [`openapi.yaml`](openapi.yaml): **{len(schema['paths'])} paths, {total} operations**.",
    "Interactive docs are served by the API at `/api/docs/` (Swagger UI) and `/api/schema/`.",
    "",
    "Authentication is JWT: `POST /api/v1/auth/login/` returns `access` and `refresh` tokens; send",
    "`Authorization: Bearer <access>`. Errors are JSON, usually `{\"error\": \"...\"}` or a DRF validation body.",
    "Login, registration, booking and payment endpoints are rate limited (HTTP 429 when exceeded).",
    "",
    "Known gap: some views have no `serializer_class`, so their request and response bodies are not described",
    "in the generated schema; the paths and methods below are complete.",
]
for key, title in GROUPS.items():
    if key not in rows:
        continue
    lines += ["", f"## {title}", "", "| Method | Path | Operation |", "|---|---|---|"]
    for method, path, summary, _ in rows[key]:
        lines.append(f"| {method} | `{path}` | {summary} |")
other = rows.get("other")
if other:
    lines += ["", "## Other", "", "| Method | Path | Operation |", "|---|---|---|"]
    lines += [f"| {m} | `{p}` | {s} |" for m, p, s, _ in other]
(ROOT / "docs/API_DOCUMENTATION.md").write_text("\n".join(lines) + "\n")
print(f"wrote docs/API_DOCUMENTATION.md ({total} operations)")
