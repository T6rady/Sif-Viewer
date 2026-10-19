"""Collect installed dependency license files for the distributable installer."""

from importlib import metadata
from pathlib import Path
import shutil
import sys


def main():
    destination = Path(__file__).resolve().parent / "licenses"
    for name in ("PySide6", "PySide6_Essentials", "shiboken6", "PyInstaller"):
        distribution = metadata.distribution(name)
        copied = 0
        for entry in distribution.files or ():
            relative = Path(str(entry))
            parts = relative.parts
            if "licenses" not in parts or ".dist-info" not in parts[0]:
                continue
            source = Path(distribution.locate_file(entry))
            if not source.is_file():
                continue
            target = destination / name / Path(*parts[parts.index("licenses") + 1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied += 1
        if not copied:
            raise RuntimeError(f"No license files found for {name}; distribution stopped.")
        print(f"{name} {distribution.version}: {copied} license file(s)")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python LICENSE.txt is missing from the base interpreter.")
    target = destination / "Python" / "LICENSE.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(python_license, target)
    versions = "\n".join(f"{name} {metadata.version(name)}" for name in
                         ("PySide6", "PySide6_Essentials", "shiboken6", "PyInstaller"))
    (destination / "versions.txt").write_text(f"Python {sys.version}\n{versions}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
