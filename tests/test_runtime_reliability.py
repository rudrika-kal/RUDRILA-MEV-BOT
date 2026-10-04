import json
import tempfile
import unittest
from pathlib import Path

from rudrila_mev.runtime_reliability import RuntimeStateStore


class RuntimeReliabilityTests(unittest.TestCase):
    def test_file_checkpoint_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            store = RuntimeStateStore(
                service_key="test",  # pragma: allowlist secret
                file_path=str(path),
            )
            store.initialize()
            store.save({"count": 7, "last_block": 123})
            loaded = store.load()
            self.assertEqual(loaded["count"], 7)
            self.assertEqual(loaded["last_block"], 123)
            self.assertIn("checkpoint_saved_at", loaded)
            self.assertEqual(store.backend, "file")

    def test_event_journal_is_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            event_path = Path(td) / "events.jsonl"
            store = RuntimeStateStore(
                service_key="test",  # pragma: allowlist secret
                file_path=str(Path(td) / "state.json"),
                event_log_path=str(event_path),
            )
            store.append_event({"event": "A", "value": 1})
            store.append_event({"event": "B", "value": 2})
            rows = [json.loads(x) for x in event_path.read_text().splitlines()]
            self.assertEqual([x["event"] for x in rows], ["A", "B"])

    def test_corrupt_checkpoint_fails_to_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            path.write_text("{broken")
            store = RuntimeStateStore(
                service_key="test",  # pragma: allowlist secret
                file_path=str(path),
            )
            self.assertIsNone(store.load())


if __name__ == "__main__":
    unittest.main()
