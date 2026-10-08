"""Regression tests for the version-gated upstream update check."""

import argparse
import os
import sys
import unittest
from unittest.mock import patch


HELPER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "update-checker", "helpers")
)
if HELPER_DIR not in sys.path:
    sys.path.insert(0, HELPER_DIR)

import update_check


class UpstreamVersionTests(unittest.TestCase):
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
    @patch.object(update_check, "fetch_latest")
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
    def test_unchanged_version_skips_commit_lookup(
        self, _load_state, _fetch_version, fetch_latest, save_state
    ):
        result = update_check.cmd_check(argparse.Namespace(now=True))

        self.assertEqual(result, 0)
        fetch_latest.assert_not_called()
        saved_state = save_state.call_args.args[0]
        self.assertEqual(saved_state["last_known_version"], "0.1.0")
        self.assertEqual(saved_state["upstream_version_etag"], '"version-etag"')
        self.assertEqual(saved_state["last_check_status"], "ok")

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

        with patch.object(update_check, "_load_state", return_value=state):
            result = update_check.cmd_check(argparse.Namespace(now=True))

        self.assertEqual(result, 1)
        fetch_latest.assert_called_once_with()
        saved_state = save_state.call_args.args[0]
        self.assertEqual(saved_state["last_known_version"], "0.2.0")
        self.assertEqual(saved_state["last_known_sha"], "new-sha")


if __name__ == "__main__":
    unittest.main()
