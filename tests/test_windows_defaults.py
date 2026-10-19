import unittest
from unittest.mock import Mock, patch

from core.windows_defaults import _association_string, is_default_sif_app


class WindowsDefaultTests(unittest.TestCase):
    def test_effective_registered_handler_is_recognized(self):
        with patch("core.windows_defaults._association_string", return_value="ORI.SIFViewer.SIF"):
            self.assertTrue(is_default_sif_app())

    def test_other_default_does_not_count_as_our_registered_app(self):
        with patch("core.windows_defaults._association_string", return_value="Other.SIF"), \
                patch("core.windows_defaults.sys.frozen", False, create=True):
            self.assertFalse(is_default_sif_app())

    def test_manual_open_with_selection_matches_packaged_executable(self):
        with patch("core.windows_defaults.sys.frozen", True, create=True), \
                patch("core.windows_defaults.sys.executable", r"C:\Apps\SIF Viewer.exe"):
            with patch("core.windows_defaults._association_string", side_effect=["Applications\\SIF Viewer.exe", r"C:\Apps\SIF Viewer.exe"]):
                self.assertTrue(is_default_sif_app())
            with patch("core.windows_defaults._association_string", side_effect=["Other.SIF", r"C:\Other\SIF Viewer.exe"]):
                self.assertFalse(is_default_sif_app())

    def test_windows_query_sizes_buffer_and_handles_unavailable_association(self):
        def query(flags, kind, extension, extra, buffer, size):
            self.assertEqual((flags, kind, extension, extra), (0, 20, ".sif", None))
            if buffer is None:
                size._obj.value = 64
                return 1
            buffer.value = "ORI.SIFViewer.SIF"
            return 0

        dll = Mock()
        dll.AssocQueryStringW.side_effect = query
        with patch("core.windows_defaults.sys.platform", "win32"), \
                patch("core.windows_defaults.ctypes.WinDLL", return_value=dll):
            self.assertEqual(_association_string(20), "ORI.SIFViewer.SIF")
            dll.AssocQueryStringW.side_effect = OSError("Unavailable")
            self.assertEqual(_association_string(20), "")
