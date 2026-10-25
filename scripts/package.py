"""Create explicit local-install ZIPs; never include credentials or development envs."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"
OUTPUT.mkdir(exist_ok=True)


def package(name: str, source: Path, prefix: str) -> None:
    with ZipFile(OUTPUT / name, "w", ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                archive.write(file, f"{prefix}/{file.relative_to(source).as_posix()}")
        for filename in ("LICENSE", "UPSTREAM.md", "README.md"):
            archive.write(ROOT / filename, f"documentation/{filename}")
    print(OUTPUT / name)


package(
    "opencook-integration-0.1.0.zip",
    ROOT / "custom_components/opencook",
    "custom_components/opencook",
)
package("opencook-addon-0.1.0.zip", ROOT / "addons/opencook", "opencook")
