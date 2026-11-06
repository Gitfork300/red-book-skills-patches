"""Regression tests for upstream update detection and acknowledgement."""

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


HELPER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "update-checker", "helpers")
)
if HELPER_DIR not in sys.path:
    sys.path.insert(0, HELPER_DIR)

import update_check


class UpstreamVersionTests(unittest.TestCase):
    def test_corrupt_state_is_not_silently_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "state.json")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("{broken")
            with patch.object(update_check, "STATE_FILE", path):
                with self.assertRaisesRegex(RuntimeError, "无法读取上游更新状态"):
                    update_check._load_state()

    def test_reads_project_version_from_pyproject(self):
        text = '[build-system]\nrequires = []\n\n[project]\nname = "xhs"\nversion = "2.4.1"\n'
        self.assertEqual(update_check._parse_upstream_version(text), "2.4.1")

    def test_rejects_missing_project_version(self):
        with self.assertRaisesRegex(RuntimeError, "no project.version"):
            update_check._parse_upstream_version("[project]\nname = 'xhs'\n")

    @patch.object(
        update_check.urllib.request,
        "urlopen",
        side_effect=update_check.urllib.error.HTTPError(
            update_check.UPSTREAM_VERSION_URL, 304, "Not Modified", {}, None
        ),
    )
    def test_not_modified_response_reuses_cached_version(self, urlopen):
        state = {
            "last_known_version": "0.1.0",
            "upstream_version_etag": '"cached-etag"',
        }

        result = update_check.fetch_upstream_version(state)

        self.assertEqual(result, {"version": "0.1.0", "etag": '"cached-etag"'})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("If-none-match"), '"cached-etag"')

    @patch.object(update_check, "_save_state")
    @patch.object(
        update_check, "fetch_latest",
        return_value={"sha": "new-sha", "iso": None, "message": "fix"},
    )
    @patch.object(
        update_check,
        "fetch_upstream_version",
        return_value={"version": "0.1.0", "etag": '"version-etag"'},
    )
    @patch.object(
        update_check,
        "_load_state",
        return_value={
            "last_known_version": "0.1.0",
            "last_known_sha": "known-sha",
            "interval_sec": 0,
        },
    )
    def test_unchanged_version_still_detects_new_commit(
        self, _load_state, _fetch_version, fetch_latest, save_state
    ):
        with contextlib.redirect_stdout(io.StringIO()):
            result = update_check.cmd_check(argparse.Namespace(now=True))

        self.assertEqual(result, 1)
        fetch_latest.assert_called_once_with()
        saved_state = save_state.call_args.args[0]
        self.assertEqual(saved_state["last_known_version"], "0.1.0")
        self.assertEqual(saved_state["upstream_version_etag"], '"version-etag"')
        self.assertEqual(saved_state["last_check_status"], "ok")
        self.assertEqual(saved_state["pending_sha"], "new-sha")

    @patch.object(update_check, "_save_state")
    @patch.object(update_check, "fetch_latest", return_value={"sha": "new-sha"})
    @patch.object(update_check, "fetch_upstream_version", return_value={"version": "0.1.0"})
    def test_pending_update_remains_until_acknowledged(self, _version, _latest, save_state):
        state = {"last_known_sha": "new-sha", "pending_sha": "new-sha", "interval_sec": 0}
        with (patch.object(update_check, "_load_state", return_value=state),
              contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(update_check.cmd_check(argparse.Namespace(now=True)), 1)
            self.assertEqual(update_check.cmd_acknowledge(argparse.Namespace(sha="old-sha")), 2)
            self.assertEqual(update_check.cmd_acknowledge(argparse.Namespace(sha="new-sha")), 0)
            self.assertEqual(update_check.cmd_check(argparse.Namespace(now=True)), 0)
        self.assertIsNone(save_state.call_args.args[0]["pending_sha"])

    @patch.object(update_check, "_save_state")
    @patch.object(update_check, "fetch_latest", return_value={"sha": "known-sha"})
    @patch.object(update_check, "fetch_upstream_version", return_value={"version": "0.1.0"})
    def test_legacy_observed_commit_requires_review(self, _version, _latest, save_state):
        state = {"last_known_sha": "known-sha", "last_notified_sha": "known-sha"}
        with patch.object(update_check, "_load_state", return_value=state), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(update_check.cmd_check(argparse.Namespace(now=True)), 1)
        self.assertEqual(save_state.call_args.args[0]["pending_sha"], "known-sha")

    @patch.object(update_check, "_load_state", return_value={
        "last_check_epoch": 99999999999, "interval_sec": 604800, "pending_sha": "new-sha"
    })
    def test_pending_update_is_reported_within_interval(self, _load_state):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(update_check.cmd_check(argparse.Namespace(now=False)), 1)

    @patch.object(update_check, "_save_state")
    @patch.object(
        update_check,
        "fetch_latest",
        return_value={"sha": "new-sha", "iso": "2026-10-08T00:00:00Z", "message": "release"},
    )
    @patch.object(
        update_check,
        "fetch_upstream_version",
        return_value={"version": "0.2.0", "etag": '"new-etag"'},
    )
    def test_changed_version_checks_commit_and_records_version(
        self, _fetch_version, fetch_latest, save_state
    ):
        state = {
            "last_known_version": "0.1.0",
            "last_known_sha": "old-sha",
            "interval_sec": 0,
        }

        output = io.StringIO()
        with patch.object(update_check, "_load_state", return_value=state), contextlib.redirect_stdout(output):
            result = update_check.cmd_check(argparse.Namespace(now=True))

        self.assertEqual(result, 1)
        fetch_latest.assert_called_once_with()
        saved_state = save_state.call_args.args[0]
        self.assertEqual(saved_state["last_known_version"], "0.2.0")
        self.assertEqual(saved_state["last_known_sha"], "new-sha")
        self.assertIn("不要直接 pull 或整仓覆盖运行层", output.getvalue())
        self.assertNotIn("小改直接 pull", output.getvalue())


if __name__ == "__main__":
    unittest.main()
