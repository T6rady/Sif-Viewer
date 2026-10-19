"""Read the effective Windows association without changing user defaults.

https://learn.microsoft.com/en-us/windows/win32/api/shlwapi/nf-shlwapi-assocquerystringw
"""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys


def _association_string(kind):
    if sys.platform != "win32":
        return ""
    try:
        query = ctypes.WinDLL("shlwapi").AssocQueryStringW
        query.argtypes = (wintypes.DWORD, ctypes.c_int, wintypes.LPCWSTR,
                          wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        query.restype = ctypes.c_long
        size = wintypes.DWORD(0)
        # S_FALSE means the required buffer size was returned.
        if query(0, kind, ".sif", None, None, ctypes.byref(size)) != 1 or not 0 < size.value <= 32768:
            return ""
        buffer = ctypes.create_unicode_buffer(size.value)
        if query(0, kind, ".sif", None, buffer, ctypes.byref(size)) == 0:
            return buffer.value
    except (OSError, AttributeError, ValueError):
        pass
    return ""


def is_default_sif_app():
    # ASSOCSTR_PROGID (20) reports the effective user-selected handler, not
    # merely an app registered as available in Open With.
    if _association_string(20).casefold() == "ori.sifviewer.sif":
        return True
    # Also recognize a packaged copy selected manually through Open With.
    if getattr(sys, "frozen", False):
        executable = _association_string(2)  # ASSOCSTR_EXECUTABLE
        if executable:
            try:
                return Path(executable).resolve() == Path(sys.executable).resolve()
            except OSError:
                pass
    return False
