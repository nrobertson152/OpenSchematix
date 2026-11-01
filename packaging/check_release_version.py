"""Verify consistent release version metadata (standard-library only)."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openschematix import VERSION


def extract(pattern, contents, label):
    match = re.search(pattern, contents, re.MULTILINE)
    if not match:
        raise SystemExit("Missing version metadata: " + label)
    return match.group(1)


def main():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    info = (ROOT / "packaging/windows_version_info.txt").read_text(encoding="utf-8")
    project_version = extract(r'^version\s*=\s*"([^"]+)"', project, "pyproject")
    file_version = extract(r"StringStruct\('FileVersion', '([^']+)'\)", info, "FileVersion")
    product_version = extract(r"StringStruct\('ProductVersion', '([^']+)'\)", info, "ProductVersion")
    filevers = tuple(int(x.strip()) for x in extract(r"filevers=\(([^)]+)\)", info, "filevers").split(","))
    prodvers = tuple(int(x.strip()) for x in extract(r"prodvers=\(([^)]+)\)", info, "prodvers").split(","))
    expected = tuple(map(int, VERSION.split("."))) + (0,)
    if VERSION != project_version or VERSION != file_version or VERSION != product_version or filevers != expected or prodvers != expected:
        raise SystemExit(f"Release versions differ: app={VERSION}, pyproject={project_version}, file={file_version}, product={product_version}, numeric={filevers}/{prodvers}")
    print(f"Release version metadata consistent: {VERSION}")


if __name__ == "__main__":
    main()
