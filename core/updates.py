"""Validate stable GitHub release tags and compare numeric app versions."""

import re

API_URL = "https://api.github.com/repos/T6rady/Sif-Viewer/releases/latest"
RELEASES_URL = "https://github.com/T6rady/Sif-Viewer/releases/latest"


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ValueError("Expected a stable version such as v1.4.5")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


def available_version(release, installed):
    """Return a newer stable version, or None. Reject malformed responses."""
    current = version_parts(installed)
    if not isinstance(release, dict):
        raise ValueError("Invalid release response")
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name")
    latest = version_parts(tag)
    return tag.removeprefix("v") if latest > current else None
