import json,tempfile,unittest
from pathlib import Path
from rudrila_mev.ci_validation import validate_strict_ci

class StrictCIValidationTests(unittest.TestCase):
    def setup_files(self):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); p=Path(td.name)
        (p/"py.txt").write_text("Ran 3 tests in 0.1s\n\nOK\n")
        (p/"forge.txt").write_text("[PASS] testA()\nSuite result: ok. 1 passed; 0 failed\n")
        (p/"bandit.json").write_text(json.dumps({"results":[]}))
        (p/"audit.json").write_text(json.dumps({"dependencies":[]}))
        (p/"secrets.json").write_text(json.dumps({"results":{}}))
        (p/"slither.json").write_text(json.dumps({"results":{"detectors":[]}}))
        (p/"tracked.txt").write_text("rudrila_mev/main.py\n")
        return p

    def call(self,p):
        return validate_strict_ci(
            python_tests_path=str(p/"py.txt"),forge_tests_path=str(p/"forge.txt"),
            bandit_path=str(p/"bandit.json"),audit_path=str(p/"audit.json"),
            secrets_path=str(p/"secrets.json"),slither_path=str(p/"slither.json"),
            tracked_files_path=str(p/"tracked.txt"))

    def test_clean_evidence_passes(self):
        self.assertTrue(self.call(self.setup_files()).accepted)

    def test_zero_or_missing_test_summary_blocks(self):
        p=self.setup_files(); (p/"py.txt").write_text("OK\n")
        with self.assertRaises(ValueError): self.call(p)

    def test_invalid_json_blocks(self):
        p=self.setup_files(); (p/"bandit.json").write_text("{")
        with self.assertRaises(ValueError): self.call(p)

    def test_bandit_medium_blocks(self):
        p=self.setup_files(); (p/"bandit.json").write_text(json.dumps({"results":[{"issue_severity":"MEDIUM"}]}))
        self.assertFalse(self.call(p).accepted)

    def test_dependency_vulnerability_blocks(self):
        p=self.setup_files(); (p/"audit.json").write_text(json.dumps({"dependencies":[{"vulns":[{"id":"X"}]}]}))
        self.assertFalse(self.call(p).accepted)

    def test_secret_blocks(self):
        p=self.setup_files(); (p/"secrets.json").write_text(json.dumps({"results":{"x.py":[{"type":"Secret Keyword","line_number":1}]}}))
        self.assertFalse(self.call(p).accepted)

    def test_slither_medium_blocks(self):
        p=self.setup_files(); (p/"slither.json").write_text(json.dumps({"results":{"detectors":[{"impact":"Medium"}]}}))
        self.assertFalse(self.call(p).accepted)

    def test_tracked_pyc_blocks(self):
        p=self.setup_files(); (p/"tracked.txt").write_text("rudrila_mev/__pycache__/x.pyc\n")
        self.assertFalse(self.call(p).accepted)

if __name__=="__main__": unittest.main()

class RuntimeScannerAttestationTests(unittest.TestCase):
    def test_attestation_passes_with_verified_sha(self):
        from rudrila_mev.ci_validation import runtime_scanner_attestation
        r=runtime_scanner_attestation(ci_verified=True,commit_sha="a"*40)
        self.assertTrue(r.accepted)

    def test_attestation_blocks_missing_verification(self):
        from rudrila_mev.ci_validation import runtime_scanner_attestation
        self.assertFalse(runtime_scanner_attestation(ci_verified=False,commit_sha="a"*40).accepted)

    def test_attestation_blocks_bad_sha(self):
        from rudrila_mev.ci_validation import runtime_scanner_attestation
        self.assertFalse(runtime_scanner_attestation(ci_verified=True,commit_sha="bad").accepted)
