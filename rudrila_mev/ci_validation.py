from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StrictCIResult:
    accepted: bool
    python_tests: int
    forge_tests: int
    bandit_medium_high: int
    dependency_vulnerabilities: int
    actionable_secrets: int
    slither_medium_high: int
    tracked_bytecode_artifacts: int
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def _read_nonempty(path: str) -> str:
    p=Path(path)
    if not p.exists() or p.stat().st_size == 0:
        raise ValueError(f"missing/empty evidence: {path}")
    return p.read_text(errors="replace")


def _json_nonempty(path: str) -> Any:
    text=_read_nonempty(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON evidence: {path}: {exc}") from exc


def python_test_count(path: str) -> int:
    text=_read_nonempty(path)
    m=re.search(r"Ran\s+(\d+)\s+tests?",text)
    if not m:
        raise ValueError("Python unittest summary missing")
    count=int(m.group(1))
    if count <= 0:
        raise ValueError("Python test count must be > 0")
    if "FAILED (" in text or "\nFAILED\n" in text:
        raise ValueError("Python tests failed")
    if "OK" not in text:
        raise ValueError("Python unittest OK marker missing")
    return count


def forge_test_count(path: str) -> int:
    text=_read_nonempty(path)
    count=len(re.findall(r"\[PASS\]",text))
    if count <= 0:
        raise ValueError("Foundry test count must be > 0")
    if "Suite result: ok" not in text:
        raise ValueError("Foundry successful suite marker missing")
    if re.search(r"\[FAIL",text):
        raise ValueError("Foundry failure found")
    return count


def validate_strict_ci(
    *,
    python_tests_path: str,
    forge_tests_path: str,
    bandit_path: str,
    audit_path: str,
    secrets_path: str,
    slither_path: str,
    tracked_files_path: str,
) -> StrictCIResult:
    reasons: list[str]=[]
    py=python_test_count(python_tests_path)
    forge=forge_test_count(forge_tests_path)

    bandit=_json_nonempty(bandit_path)
    if not isinstance(bandit,dict) or "results" not in bandit:
        raise ValueError("Bandit JSON schema invalid")
    bbad=[x for x in bandit.get("results",[]) if str(x.get("issue_severity","")).upper() in {"MEDIUM","HIGH"}]

    audit=_json_nonempty(audit_path)
    if not isinstance(audit,dict) or "dependencies" not in audit:
        raise ValueError("pip-audit JSON schema invalid")
    abad=sum(len(x.get("vulns",[]) or []) for x in audit.get("dependencies",[]) if isinstance(x,dict))

    secrets=_json_nonempty(secrets_path)
    if not isinstance(secrets,dict) or "results" not in secrets:
        raise ValueError("detect-secrets JSON schema invalid")
    sbad=[]
    for fn,rows in (secrets.get("results",{}) or {}).items():
        for row in rows:
            if fn in {"config.json","config.example.json"} and row.get("type")=="Secret Keyword":
                continue
            sbad.append((fn,row.get("line_number"),row.get("type")))

    slither=_json_nonempty(slither_path)
    if not isinstance(slither,dict) or "results" not in slither:
        raise ValueError("Slither JSON schema invalid")
    detectors=((slither.get("results",{}) or {}).get("detectors",[]) or [])
    slbad=[x for x in detectors if str(x.get("impact","")).lower() in {"high","medium"}]

    tracked=_read_nonempty(tracked_files_path).splitlines()
    bytecode=[x for x in tracked if "__pycache__" in x or x.endswith(".pyc")]

    if bbad: reasons.append(f"BLOCK: Bandit medium/high={len(bbad)}")
    if abad: reasons.append(f"BLOCK: dependency vulnerabilities={abad}")
    if sbad: reasons.append(f"BLOCK: actionable secret candidates={len(sbad)}")
    if slbad: reasons.append(f"BLOCK: Slither medium/high={len(slbad)}")
    if bytecode: reasons.append(f"BLOCK: tracked Python bytecode artifacts={len(bytecode)}")

    accepted=not reasons
    if accepted:
        reasons.append("PASS: strict scanner schemas, actual tests, security findings and repo hygiene verified")
    return StrictCIResult(
        accepted=accepted,python_tests=py,forge_tests=forge,
        bandit_medium_high=len(bbad),dependency_vulnerabilities=abad,
        actionable_secrets=len(sbad),slither_medium_high=len(slbad),
        tracked_bytecode_artifacts=len(bytecode),reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class RuntimeScannerAttestation:
    accepted: bool
    ci_verified: bool
    commit_sha: str | None
    reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def runtime_scanner_attestation(
    *, ci_verified: bool, commit_sha: str | None
) -> RuntimeScannerAttestation:
    sha=(commit_sha or "").strip().lower()
    reasons=[]
    if not ci_verified:
        reasons.append("BLOCK: strict scanner CI attestation is not enabled")
    if not re.fullmatch(r"[0-9a-f]{40}",sha):
        reasons.append("BLOCK: strict scanner CI commit SHA is missing/invalid")
    accepted=not reasons
    if accepted:
        reasons.append("PASS: strict scanner CI attestation pinned to immutable commit")
    return RuntimeScannerAttestation(
        accepted=accepted,ci_verified=bool(ci_verified),
        commit_sha=sha or None,reasons=tuple(reasons))
