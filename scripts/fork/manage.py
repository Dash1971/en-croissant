#!/usr/bin/env python3
"""Review-only fork candidates and evidence. Never installs, signs with a key, or publishes."""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scripts/fork/out"
LOCKS = ("pnpm-lock.yaml", "src-tauri/Cargo.lock")
OVERLAY = "src-tauri/tauri.maintained.conf.json"
FEATURE = "maintained-fork"
MANUAL_GATES = {"real_engines": "pending", "copied_databases": "pending", "owner_release_approval": "pending"}


def run(args, cwd=None, env=None):
    cwd = cwd or ROOT
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=True).stdout.strip()


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def revision(ref, root=None):
    root = root or ROOT
    return run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], root)


def clean_source(root=None):
    root = root or ROOT
    # No user-supplied excludes, reset, stash or cleanup of source files.
    dirty = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], root)
    if dirty:
        raise ValueError(f"Candidate requires clean tracked/staged/untracked source:\n{dirty}")


def source_identity(root=None):
    root = root or ROOT
    clean_source(root)
    register = read_json(root / "docs/fork/changes.json")
    upstream = revision(register["upstream"]["commit"], root)
    head = revision("HEAD", root)
    run(["git", "merge-base", "--is-ancestor", upstream, head], root)
    return {
        "fork_commit": head,
        "fork_tree": run(["git", "rev-parse", "HEAD^{tree}"], root),
        "upstream_commit": upstream,
        "lockfiles": {path: digest(root / path) for path in LOCKS},
    }


def check_register(root=None):
    root = root or ROOT
    register = read_json(root / "docs/fork/changes.json")
    upstream = revision(register["upstream"]["commit"], root)
    head = revision("HEAD", root)
    run(["git", "merge-base", "--is-ancestor", upstream, head], root)
    patterns = register["maintenance_paths"] + [p for change in register["changes"] for p in change["paths"]]
    paths = run(["git", "diff", "--name-only", upstream, head], root).splitlines()
    missing = [p for p in paths if not any(fnmatch.fnmatchcase(p, pattern) for pattern in patterns)]
    if missing:
        raise ValueError("Unregistered upstream delta: " + ", ".join(missing))
    return {"upstream_commit": upstream, "fork_commit": head, "changed_paths": paths}


def validate_distribution(root=None):
    root = root or ROOT
    overlay = read_json(root / OVERLAY)
    base = read_json(root / "src-tauri/tauri.conf.json")
    if overlay.get("version") != "0.16.1-fork.1":
        raise ValueError("Unexpected maintained candidate version")
    if overlay.get("bundle", {}).get("createUpdaterArtifacts") is not False:
        raise ValueError("Candidate must disable updater artifacts")
    if overlay.get("plugins", {}).get("updater", {}).get("endpoints") != []:
        raise ValueError("Candidate must have no updater feed")
    if overlay.get("identifier", base["identifier"]) != base["identifier"]:
        raise ValueError("Candidate cannot change the application identifier")
    if base["bundle"]["macOS"].get("signingIdentity") != "-":
        raise ValueError("Only ad-hoc signing is allowed for this candidate")
    if overlay.get("bundle", {}).get("macOS", {}).get("signingIdentity", "-") != "-":
        raise ValueError("Only ad-hoc signing is allowed for this candidate")
    configured = os.environ.get("VITE_EN_CROISSANT_DISTRIBUTION")
    if configured not in (None, FEATURE):
        raise ValueError("Conflicting frontend distribution environment")
    for key in os.environ:
        if key.startswith(("TAURI_SIGNING_PRIVATE_KEY", "APPLE_CERTIFICATE", "APPLE_API_", "APPLE_PASSWORD", "APPLE_ID", "APPLE_SIGNING_IDENTITY")):
            raise ValueError(f"Signing/notarization environment is not allowed: {key}")
    return overlay["version"]


def app_manifest(app):
    """Digest file content, executable mode and symlink targets, excluding timestamps."""
    app = Path(app)
    entries = []
    for path in sorted(app.rglob("*")):
        relative = path.relative_to(app).as_posix()
        info = path.lstat()
        if path.is_symlink():
            target = os.readlink(path)
            if not path.resolve().is_relative_to(app.resolve()):
                raise ValueError(f"Bundle symlink escapes the app: {relative}")
            entries.append({"path": relative, "type": "symlink", "target": target})
        elif path.is_file():
            entries.append({"path": relative, "type": "file", "mode": stat.S_IMODE(info.st_mode), "sha256": digest(path)})
        elif not path.is_dir():
            raise ValueError(f"Unexpected bundle entry: {relative}")
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "entries": entries}


def validate_bundled_extension(app, pinned):
    extension = Path(app) / "Contents/Resources/aixchess.duckdb_extension"
    if extension.stat().st_size != pinned["size"] or digest(extension) != pinned["sha256"]:
        raise ValueError("Bundled AIX extension differs from the pinned input")


def verify_app(app, expected_version):
    if platform.system() != "Darwin":
        raise ValueError("Bundle verification requires macOS codesign and lipo")
    app = Path(app)
    with (app / "Contents/Info.plist").open("rb") as source:
        info = plistlib.load(source)
    if info["CFBundleIdentifier"] != "org.encroissant.app":
        raise ValueError("Wrong application identifier")
    if info["CFBundleShortVersionString"] != expected_version:
        raise ValueError("Wrong candidate bundle version")
    executable = app / "Contents/MacOS" / info["CFBundleExecutable"]
    if not executable.stat().st_mode & 0o111:
        raise ValueError("Candidate executable has no execute permission")
    validate_bundled_extension(app, read_json(ROOT / "scripts/fork/inputs.json")["aix"])
    if run(["lipo", "-archs", str(executable)]) != "arm64":
        raise ValueError("Candidate must contain exactly the arm64 architecture")
    run(["codesign", "--verify", "--deep", "--strict", str(app)])
    result = subprocess.run(["codesign", "-dv", "--verbose=4", str(app)], capture_output=True, text=True, check=True)
    details = result.stdout + result.stderr
    if "Signature=adhoc" not in details:
        raise ValueError("Expected ad-hoc candidate signature")
    return {"app": app_manifest(app), "executable_sha256": digest(executable), "signing": "ad-hoc", "notarized": False, "codesign_details": details}


def logged_step(name, args, output, env):
    log = output / "logs" / f"{name}.log"
    log.parent.mkdir(exist_ok=True)
    print(f"Running {name}", flush=True)
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record = {"name": name, "command": args, "exit_code": result.returncode, "log": str(log.relative_to(output)), "sha256": digest(log)}
    if result.returncode:
        write_json(output / "failed-step.json", record)
        raise ValueError(f"{name} failed; see {log}")
    return record


def validate_lifecycle_log(log):
    expected = re.findall(r"async fn (engine_lifecycle_\w+)\(", (ROOT / "src-tauri/src/chess_lifecycle_tests.rs").read_text())
    text = Path(log).read_text()
    if len(expected) < 10 or any(not re.search(rf"test \S*{re.escape(name)} \.\.\. ok", text) for name in expected):
        raise ValueError("Native test log must show every lifecycle regression passing (at least ten)")


def pinned_extension(inputs):
    path = ROOT / "aixchess.duckdb_extension"
    if not path.exists():
        # Download only the recorded asset. Never follow a mutable latest tag.
        with urllib.request.urlopen(inputs["url"]) as response, tempfile.NamedTemporaryFile(dir=OUT, delete=False) as temp:
            shutil.copyfileobj(response, temp)
            temporary = Path(temp.name)
        try:
            if temporary.stat().st_size != inputs["size"] or digest(temporary) != inputs["sha256"]:
                raise ValueError("Pinned AIX download digest/size mismatch")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if path.stat().st_size != inputs["size"] or digest(path) != inputs["sha256"]:
        raise ValueError("Existing AIX extension differs from the pinned candidate input")


def command_recipe():
    return [
        ("dependencies", ["pnpm", "install", "--frozen-lockfile", "--store-dir", "scripts/fork/out/cache/pnpm"]),
        ("register", ["python3", "scripts/fork/manage.py", "register-check"]),
        ("receipt-tests", ["python3", "-m", "unittest", "discover", "-s", "scripts/fork", "-p", "test_*.py"]),
        ("frontend-lint", ["pnpm", "lint:ci"]),
        ("frontend-tests", ["pnpm", "test"]),
        ("frontend-build", ["pnpm", "build-vite"]),
        ("native-tests", ["cargo", "test", "--release", "--manifest-path", "src-tauri/Cargo.toml", "--locked", "--features", FEATURE, "--", "--test-threads=2"]),
        ("native-build", ["pnpm", "exec", "tauri", "build", "--bundles", "app", "--features", FEATURE, "--config", OVERLAY, "--", "--locked"]),
    ]


def validate_recipe(steps):
    expected = command_recipe()
    if [step.get("name") for step in steps] != [name for name, _ in expected]:
        raise ValueError("Validation steps must be unique, complete and in recipe order")
    for step, (name, command) in zip(steps, expected):
        if step.get("command") != command:
            raise ValueError(f"Validation command differs from the maintained recipe: {name}")


def stage_previous_bundle(built, output):
    # Preserve prior generated output, but never accept it as this build's app.
    # This also fails closed if a layered Cargo config redirects the new output.
    if built.exists() or built.is_symlink():
        shutil.move(str(built), str(output / "previous-build.app"))


def developer_tools():
    # Command Line Tools can build this app without a full Xcode installation.
    xcode = subprocess.run(["xcodebuild", "-version"], capture_output=True, text=True)
    return {"developer_dir": run(["xcode-select", "-p"]),
            "sdk": run(["xcrun", "--show-sdk-version"]),
            "xcodebuild": {"exit_code": xcode.returncode, "stdout": xcode.stdout, "stderr": xcode.stderr}}


def candidate():
    inputs = read_json(ROOT / "scripts/fork/inputs.json")
    identity = source_identity()
    check_register()
    version = validate_distribution()
    if os.environ.get("CARGO_BUILD_TARGET"):
        raise ValueError("CARGO_BUILD_TARGET must be unset for the native candidate recipe")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("Candidate must run natively on Apple Silicon macOS")
    if (ROOT / "node_modules").is_symlink():
        raise ValueError("Use an independent checkout, not a shared node_modules symlink")
    versions = {"node": run(["node", "--version"]).removeprefix("v"), "pnpm": run(["pnpm", "--version"]), "rust": run(["rustc", "--version"]).split()[1]}
    if any(versions[key] != inputs[key] for key in versions):
        raise ValueError(f"Tool versions differ from inputs.json: {versions}")
    if read_json(ROOT / "package.json")["packageManager"] != f"pnpm@{inputs['pnpm']}":
        raise ValueError("packageManager and candidate pnpm pin disagree")
    rust_details = run(["rustc", "-vV"])
    if f"host: {inputs['target']}" not in rust_details:
        raise ValueError("Rust compiler must target the native arm64 macOS host")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUT / f"candidate-{identity['fork_commit'][:12]}-{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    cargo_home = Path(env.get("CARGO_HOME", str(OUT / "cache/cargo"))).expanduser()
    cargo_target = Path(env.get("CARGO_TARGET_DIR", str(ROOT / "src-tauri/target"))).expanduser()
    cargo_home = (ROOT / cargo_home).resolve()
    cargo_target = (ROOT / cargo_target).resolve()
    env.update({"VITE_EN_CROISSANT_DISTRIBUTION": FEATURE, "CARGO_HOME": str(cargo_home), "CARGO_TARGET_DIR": str(cargo_target), "CARGO_BUILD_JOBS": "2", "AIX_EXTENSION_TARGET": "osx_arm64", "AIX_EXTENSION_TAG": inputs["aix"]["tag"], "AIX_EXTENSION_FORCE_DOWNLOAD": "0", "CI": "true"})
    pinned_extension(inputs["aix"])
    steps = []
    built = Path(env["CARGO_TARGET_DIR"]) / "release/bundle/macos/en-croissant.app"
    for name, args in command_recipe():
        if name == "native-build":
            stage_previous_bundle(built, output)
        steps.append(logged_step(name, args, output, env))
        if name == "native-tests":
            validate_lifecycle_log(output / steps[-1]["log"])
    if identity != source_identity():
        raise ValueError("Source/lockfiles changed during validation/build")
    if not built.is_dir() or built.is_symlink():
        raise ValueError("Build did not produce a fresh native app at the expected output path")
    app = output / "en-croissant.app"
    shutil.copytree(built, app, symlinks=True)
    bundle = verify_app(app, version)
    archive = output / "en-croissant-arm64-candidate.zip"
    run(["ditto", "-c", "-k", "--norsrc", "--keepParent", str(app), str(archive)])
    receipt = {"schema_version": 1, "kind": "unpublished-candidate", "created_at": stamp, **identity, "version": version, "distribution": FEATURE, "target": inputs["target"], "tools": versions, "cargo": run(["cargo", "--version"]), "rust_details": rust_details, "python": platform.python_version(), "git": run(["git", "--version"]), "macos": platform.mac_ver()[0], "developer_tools": developer_tools(), "inputs": inputs, "checks": steps, "manual_gates": MANUAL_GATES.copy(), "published": False, "installed": False, "bundle": bundle, "archive": {"path": archive.name, "sha256": digest(archive)}}
    write_json(output / "receipt.json", receipt)
    verify(output / "receipt.json")
    print(output / "receipt.json")


def verify(receipt_path):
    receipt_path = Path(receipt_path).resolve()
    receipt = read_json(receipt_path)
    if receipt["kind"] != "unpublished-candidate" or receipt["published"] or receipt["installed"]:
        raise ValueError("Not an unpublished, uninstalled candidate")
    if receipt["manual_gates"] != MANUAL_GATES:
        raise ValueError("Candidate tool cannot certify manual gates")
    if receipt["distribution"] != FEATURE or receipt["target"] != "aarch64-apple-darwin":
        raise ValueError("Wrong candidate distribution/target")
    if receipt["fork_commit"] != revision("HEAD") or receipt["fork_tree"] != run(["git", "rev-parse", "HEAD^{tree}"]):
        raise ValueError("Check out the receipt's exact commit/tree before verification")
    if {key: receipt[key] for key in source_identity()} != source_identity():
        raise ValueError("Source or locks do not match receipt")
    if receipt["version"] != validate_distribution():
        raise ValueError("Receipt version differs from distribution overlay")
    expected_inputs = read_json(ROOT / "scripts/fork/inputs.json")
    if receipt["inputs"] != expected_inputs or any(receipt["tools"][k] != expected_inputs[k] for k in ("rust", "node", "pnpm")):
        raise ValueError("Receipt tool/input pins do not match source")
    validate_recipe(receipt["checks"])
    for step in receipt["checks"]:
        log = safe_artifact(receipt_path.parent, step["log"])
        if step["exit_code"] != 0 or digest(log) != step["sha256"]:
            raise ValueError("Failed or modified validation log")
    native = next(s for s in receipt["checks"] if s["name"] == "native-tests")
    validate_lifecycle_log(safe_artifact(receipt_path.parent, native["log"]))
    archive = safe_artifact(receipt_path.parent, receipt["archive"]["path"])
    if digest(archive) != receipt["archive"]["sha256"]:
        raise ValueError("Archive digest mismatch")
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "en-croissant.app":
                raise ValueError("Unsafe candidate archive path")
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = PurePosixPath(zipped.read(entry).decode())
                if target.is_absolute() or ".." in target.parts:
                    raise ValueError("Unsafe candidate archive symlink")
    with tempfile.TemporaryDirectory() as directory:
        run(["ditto", "-x", "-k", str(archive), directory])
        actual = verify_app(Path(directory) / "en-croissant.app", receipt["version"])
        for field in ("app", "executable_sha256", "signing", "notarized"):
            if actual[field] != receipt["bundle"][field]:
                raise ValueError(f"Extracted bundle {field} differs from receipt")
    original_app = receipt_path.parent / "en-croissant.app"
    if original_app.exists() and app_manifest(original_app) != receipt["bundle"]["app"]:
        raise ValueError("Candidate app differs from archived app")
    print("Verified candidate hashes, source, check logs and ad-hoc signature; manual gates remain pending.")


def safe_artifact(directory, name):
    path = directory / name
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Receipt path escapes artifact directory")
    return path


def drift(output, upstream_ref=None):
    report = {"schema_version": 1, "kind": "read-only-upstream-drift", "status": "error", "fork_commit": None, "registered_upstream_commit": None, "upstream_commit": None}
    try:
        register = read_json(ROOT / "docs/fork/changes.json")
        report["fork_commit"] = revision("HEAD")
        report["registered_upstream_commit"] = revision(register["upstream"]["commit"])
        if upstream_ref:
            report["upstream_commit"] = revision(upstream_ref)
        else:
            upstream = register["upstream"]
            advertised = run(["git", "ls-remote", "--exit-code", upstream["repository"], f"refs/heads/{upstream['branch']}"])
            sha = advertised.split()[0]
            run(["git", "fetch", "--no-tags", "--no-write-fetch-head", upstream["repository"], sha])
            report["upstream_commit"] = revision(sha)
        report["merge_base"] = run(["git", "merge-base", report["fork_commit"], report["upstream_commit"]])
        comparison = subprocess.run(["git", "merge-tree", "--write-tree", report["fork_commit"], report["upstream_commit"]], cwd=ROOT, capture_output=True, text=True)
        report["merge_tree_exit_code"] = comparison.returncode
        report["merge_tree_stdout"] = comparison.stdout
        report["merge_tree_stderr"] = comparison.stderr
        if comparison.returncode not in (0, 1):
            raise ValueError("merge-tree failed; see recorded stderr")
        report["upstream_changed_paths"] = run(["git", "diff", "--name-only", report["registered_upstream_commit"], report["upstream_commit"]]).splitlines()
        report["status"] = "clean" if comparison.returncode == 0 else "conflicts"
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        report["error"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            report["command_stderr"] = error.stderr
    finally:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        write_json(output, report)
    if report["status"] == "error":
        raise ValueError(f"Drift check failed; report: {output}")
    print(f"Drift: {report['status']}; report: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("candidate")
    sub.add_parser("register-check")
    check = sub.add_parser("verify")
    check.add_argument("receipt", type=Path)
    compare = sub.add_parser("drift")
    compare.add_argument("--output", type=Path, default=OUT / "drift.json")
    compare.add_argument("--upstream-ref", help="Already-fetched revision; omit to fetch registered upstream branch")
    args = parser.parse_args()
    if args.command == "candidate":
        candidate()
    elif args.command == "register-check":
        print(json.dumps(check_register(), indent=2))
    elif args.command == "verify":
        verify(args.receipt)
    else:
        drift(args.output, args.upstream_ref)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
