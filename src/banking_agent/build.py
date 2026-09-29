"""
Builds what Terraform deploys into build/ (ADR-0004, Deployment): a zip each for the Runtime and the Lambdas, with this
package and the Linux arm64 wheels its dependency group locks in uv.lock. Every zip is the same bytes on every machine,
so a plan shows a change only when the code or a locked version changed. It also rewrites the Gateway's tool
definitions, which are committed so that CI can lint the stack without a build.
"""

import json
import shutil
import subprocess
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from banking_agent.contracts.gateway import tool_definitions

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
GATEWAY_TOOLS = ROOT / "infra" / "modules" / "gateway" / "tools.json"
PLATFORM = (
    "--python-platform",
    "aarch64-manylinux2014",
    "--python-version",
    "3.13",
    "--only-binary",
    ":all:",
)
EPOCH = (2026, 1, 1, 0, 0, 0)

Run = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class Artifact:
    name: str
    group: str | None = None
    entry: str | None = None


ARTIFACTS = (
    Artifact(
        "runtime",
        group="agent",
        entry="from banking_agent.agent.app import main\n\nmain()\n",
    ),
    Artifact("pre_token"),
    Artifact("reads", group="tools"),
)


def run(command: Sequence[str]) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def packaged(path: Path, root: Path) -> bool:
    """
    Console scripts carry the building machine's interpreter in their shebang, and nothing runs them.
    """
    parts = path.relative_to(root).parts
    return path.is_file() and parts[0] != "bin" and "__pycache__" not in parts


def write_zip(source: Path, target: Path) -> None:
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in source.rglob("*") if packaged(p, source)):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=EPOCH)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build_wheel(out: Path, run: Run = run) -> Path:
    run(["uv", "build", "--quiet", "--wheel", "--clear", "--out-dir", str(out)])
    return next(out.glob("banking_agent-*.whl"))


def build_artifact(artifact: Artifact, wheel: Path, out: Path, run: Run = run) -> Path:
    work = out / artifact.name
    package = work / "package"
    shutil.rmtree(work, ignore_errors=True)
    package.mkdir(parents=True)
    if artifact.group is not None:
        requirements = work / "requirements.txt"
        run(
            [
                "uv",
                "export",
                "--frozen",
                "--only-group",
                artifact.group,
                "--no-emit-project",
                "--no-header",
                "--no-annotate",
                "--quiet",
                "--output-file",
                str(requirements),
            ]
        )
        run(
            [
                "uv",
                "pip",
                "install",
                "--quiet",
                *PLATFORM,
                "--target",
                str(package),
                "-r",
                str(requirements),
            ]
        )
    # Unpacked rather than installed: an install records the wheel's local path in direct_url.json.
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(package)
    if artifact.entry is not None:
        (package / "main.py").write_text(artifact.entry, encoding="utf-8")
    target = out / f"{artifact.name}.zip"
    write_zip(package, target)
    return target


def gateway_tools() -> str:
    return json.dumps(tool_definitions(), indent=2) + "\n"


def main(out: Path = BUILD, tools: Path = GATEWAY_TOOLS, run: Run = run) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    wheel = build_wheel(out / "dist", run)
    built = [build_artifact(a, wheel, out, run) for a in ARTIFACTS]
    for path in built:
        print(f"{path.relative_to(out.parent)} {path.stat().st_size / 1e6:.1f} MB")
    tools.write_text(gateway_tools(), encoding="utf-8")
    return built


if __name__ == "__main__":
    main()
