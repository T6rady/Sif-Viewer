"""Update checks use mocked replies and never need Internet access."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import Mock

from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from core.updates import available_version
from ui.update_checker import UpdateChecker


class UpdateTests(unittest.TestCase):
    def test_numeric_comparison_and_stable_releases(self):
        for tag, expected in [("v1.4.6", "1.4.6"), ("1.10.0", "1.10.0"),
                              ("v1.4.5", None), ("1.3.9", None)]:
            self.assertEqual(available_version({"tag_name": tag}, "1.4.5"), expected)
        for flag in ("draft", "prerelease"):
            self.assertIsNone(available_version({"tag_name": "v2.0.0", flag: True}, "1.4.5"))

    def test_invalid_responses(self):
        for response in [None, [], {}, {"tag_name": "v1.5.0-rc1"}, {"tag_name": 123}]:
            with self.assertRaises(ValueError):
                available_version(response, "1.4.5")

    def test_async_completion_and_failures(self):
        app = QApplication.instance() or QApplication([])
        checker = UpdateChecker("1.4.5")
        results = []
        checker.completed.connect(lambda version, error: results.append((version, error)))
        for payload, network_error, expected in [
            (b'{"tag_name":"v1.5.0"}', QNetworkReply.NetworkError.NoError, "1.5.0"),
            (b'not json', QNetworkReply.NetworkError.NoError, None),
            (b'', QNetworkReply.NetworkError.TimeoutError, None),
        ]:
            reply = Mock()
            reply.attribute.return_value = 200
            reply.error.return_value = network_error
            reply.readAll.return_value = payload
            checker.reply = reply
            checker._finished()
            self.assertEqual(results[-1][0], expected)
            self.assertEqual(bool(results[-1][1]), expected is None)
            self.assertIsNone(checker.reply)
            reply.deleteLater.assert_called_once()

    def test_github_http_errors_are_not_reported_as_connection_failures(self):
        app = QApplication.instance() or QApplication([])
        checker = UpdateChecker("1.4.5")
        results = []
        checker.completed.connect(lambda version, error: results.append((version, error)))
        for status, expected in [(404, "public release"), (403, "limited or denied"),
                                 (429, "limited or denied")]:
            reply = Mock()
            reply.attribute.return_value = status
            reply.error.return_value = QNetworkReply.NetworkError.ContentNotFoundError
            checker.reply = reply
            checker._finished()
            self.assertIsNone(results[-1][0])
            self.assertIn(expected, results[-1][1])


if __name__ == "__main__":
    unittest.main()
