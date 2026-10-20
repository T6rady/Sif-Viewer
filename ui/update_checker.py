"""Asynchronous, bounded GitHub update checks using Qt's network event loop."""

import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from core.updates import API_URL, available_version


class UpdateChecker(QObject):
    completed = Signal(object, str)  # newer version (or None), error

    def __init__(self, installed, parent=None):
        super().__init__(parent)
        self.installed = installed
        self.manager = QNetworkAccessManager(self)
        self.reply = None

    def check(self):
        if self.reply is not None:
            return
        request = QNetworkRequest(QUrl(API_URL))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"ORI-SIF-Viewer")
        request.setTransferTimeout(10000)
        self.reply = self.manager.get(request)
        self.reply.readyRead.connect(self._limit_response)
        self.reply.finished.connect(self._finished)

    def _limit_response(self):
        if self.reply is not None and self.reply.bytesAvailable() > 1024 * 1024:
            self.reply.abort()

    def cancel(self):
        if self.reply is not None:
            self.reply.abort()

    def _finished(self):
        reply, self.reply = self.reply, None
        version, error = None, ""
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status == 404:
                error = ("GitHub could not find a public release for T6rady/Sif-Viewer. "
                         "The repository may be private or renamed, or have no published stable release. "
                         "The app publisher needs to provide a publicly accessible release source.")
            elif status in (403, 429):
                error = "GitHub has limited or denied this update request. Please try again later."
            elif reply.error() != QNetworkReply.NetworkError.NoError:
                error = ("Could not check for updates. Check your Internet connection or try again later.\n\n"
                         f"Details: {reply.errorString()}")
            else:
                data = bytes(reply.readAll())
                if len(data) > 1024 * 1024:
                    raise ValueError("Response too large")
                version = available_version(json.loads(data), self.installed)
        except (ValueError, TypeError, OverflowError):
            error = "GitHub returned an unrecognized release version. Please check the releases page."
        finally:
            reply.deleteLater()
        self.completed.emit(version, error)
