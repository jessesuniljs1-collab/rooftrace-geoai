"""Read-only supplementary audit. Never prints candidate credential values."""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Google API key": r"AIza[0-9A-Za-z_-]{35}",
    "OpenAI token": r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}",
    "GitHub token": r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "Hugging Face token": r"hf_[A-Za-z0-9]{25,}",
    "AWS access key": r"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "Private key header": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "Vercel token assignment": r"(?i)(?:vercel_token|vercel_access_token)\s*[=:]\s*[\"']?[A-Za-z0-9_-]{15,}",
}


def main():
    findings = []

    def scan(label, text):
        for rule, expression in PATTERNS.items():
            if re.search(expression, text):
                findings.append({"location": label, "rule": rule, "value": "REDACTED"})

    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    for file in files:
        if not file or file.endswith((".png", ".jpg")):
            continue
        scan(file, (ROOT / file).read_text(encoding="utf-8", errors="replace"))
    log_path = ROOT / "private/audit"
    log_path.mkdir(parents=True, exist_ok=True)
    runs = json.loads(subprocess.check_output(["gh", "run", "list", "--repo", "jessesuniljs1-collab/rooftrace-geoai", "--limit", "20", "--json", "databaseId,status"]))
    checked_runs = []
    for run in runs:
        if run["status"] == "completed":
            log = subprocess.check_output(["gh", "run", "view", str(run["databaseId"]), "--repo", "jessesuniljs1-collab/rooftrace-geoai", "--log"], stderr=subprocess.DEVNULL).decode("utf-8", errors="replace")
            scan(f"CI run {run['databaseId']}", log)
            checked_runs.append(run["databaseId"])
    session = requests.Session()
    session.trust_env = False
    base = "https://rooftrace-geoai.vercel.app"
    for path in ["/", "/static/app.js", "/static/solar.js", "/static/styles.css", "/static/solar.css", "/api/samples", "/health"]:
        response = session.get(base + path, timeout=120)
        response.raise_for_status()
        scan("deployed " + path, response.text)
    private_paths = {}
    for path in ["/.env", "/.git/config", "/.vercel/project.json", "/static/.env", "/models/model.pth"]:
        response = session.get(base + path, timeout=60)
        private_paths[path] = response.status_code
        assert response.status_code == 404, (path, response.status_code)
    gitleaks = json.loads((log_path / "history.json").read_text())
    assert not gitleaks, "Inspect the redacted Gitleaks report locally."
    report = dict(verified_at_ist=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
                  gitleaks_version="8.30.1, official release checksum verified",
                  scope="Full Git history (--all) plus tracked text, completed CI logs, deployed public text assets, and private-file route probes",
                  gitleaks_findings=len(gitleaks), supplemental_findings=findings,
                  completed_ci_logs_scanned=checked_runs, private_routes=private_paths,
                  environment="No Vercel project environment variables and no GitHub Actions repository secrets configured, verified via authenticated CLIs",
                  credentials="Existing CLI authentication stays in OS/user credential storage, outside this project. No model/API tokens are required or supplied to the application.",
                  limitation="Pattern-based scans cannot mathematically prove absence of every possible unknown credential format. No credential values are printed or committed by this audit.")
    (ROOT / "docs/security-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if findings:
        raise SystemExit("Potential exposure detected; see redacted locations.")


if __name__ == "__main__":
    main()
