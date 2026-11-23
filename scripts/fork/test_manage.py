"""Small local fixtures: no app, network, Rust compiler, credentials or private data."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
import unittest
from unittest.mock import patch

import manage


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.override = patch.object(manage, "ROOT", self.root)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("source.txt", "base\n")
        self.write("pnpm-lock.yaml", "fixture lock\n")
        self.write("src-tauri/Cargo.lock", "fixture lock\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD")
        self.write("docs/fork/changes.json", json.dumps({
            "upstream": {"commit": self.base, "repository": "unused", "branch": "main"},
            "maintenance_paths": ["docs/fork/**", ".gitignore", "scripts/fork/**"],
            "changes": [{"paths": ["source.txt"]}],
        }))
        self.write(".gitignore", "scripts/fork/out/\n")
        self.commit("register")

    def git(self, *args):
        return manage.run(["git", *args], cwd=self.root)

    def write(self, path, value):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value)
        return destination

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)

    def test_clean_source_rejects_untracked_staged_and_unstaged(self):
        before = manage.source_identity()
        self.write("new-source.ts", "untracked")
        with self.assertRaisesRegex(ValueError, "untracked"):
            manage.clean_source()
        self.git("add", "new-source.ts")
        with self.assertRaises(ValueError):
            manage.clean_source()
        self.commit("new source")
        self.write("source.txt", "changed")
        with self.assertRaises(ValueError):
            manage.clean_source()
        self.assertEqual(self.git("show", f"{before['fork_commit']}:source.txt"), "base")

    def test_only_specific_generated_output_is_ignored(self):
        self.write("scripts/fork/out/log.txt", "output")
        manage.clean_source()
        self.write("scripts/fork/unknown.py", "source")
        with self.assertRaises(ValueError):
            manage.clean_source()

    def test_identity_records_exact_commit_tree_upstream_and_locks(self):
        result = manage.source_identity()
        self.assertEqual(result["fork_commit"], self.git("rev-parse", "HEAD"))
        self.assertEqual(result["fork_tree"], self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(result["upstream_commit"], self.base)
        self.assertEqual(result["lockfiles"]["pnpm-lock.yaml"], manage.digest(self.root / "pnpm-lock.yaml"))

    def test_register_rejects_unregistered_committed_delta(self):
        manage.check_register()
        self.write("unregistered.rs", "new code")
        self.commit("unregistered")
        with self.assertRaisesRegex(ValueError, "unregistered.rs"):
            manage.check_register()

    def test_drift_reports_conflict_with_exact_revisions_without_touching_branch(self):
        self.git("checkout", "-b", "upstream", self.base)
        self.write("source.txt", "upstream edit\n")
        self.commit("upstream")
        upstream = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.write("source.txt", "maintained edit\n")
        self.commit("maintained")
        head = self.git("rev-parse", "HEAD")
        output = self.root / "scripts/fork/out/drift.json"
        manage.drift(output, upstream)
        report = manage.read_json(output)
        self.assertEqual(report["status"], "conflicts")
        self.assertEqual(report["merge_tree_exit_code"], 1)
        self.assertEqual(report["fork_commit"], head)
        self.assertEqual(report["upstream_commit"], upstream)
        self.assertIn("source.txt", report["merge_tree_stdout"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        manage.clean_source()

    def test_drift_failure_is_not_reported_as_zero_conflicts(self):
        output = self.root / "scripts/fork/out/drift.json"
        with self.assertRaisesRegex(ValueError, "Drift check failed"):
            manage.drift(output, "missing-revision")
        report = manage.read_json(output)
        self.assertEqual(report["status"], "error")
        self.assertNotIn("upstream_changed_paths", report)
        self.assertIsNone(report["upstream_commit"])
        self.assertIn("error", report)

    def test_receipt_verifies_roundtrip_and_rejects_log_archive_and_source_tampering(self):
        inputs = {"rust": "1.99.1", "node": "24.22.3", "pnpm": "12.15.0"}
        self.write("scripts/fork/inputs.json", json.dumps(inputs))
        names = [f"engine_lifecycle_case_{i}" for i in range(10)]
        self.write("src-tauri/src/chess_lifecycle_tests.rs", "\n".join(f"async fn {name}() {{}}" for name in names))
        self.commit("fixture inputs")
        output = self.root / "scripts/fork/out/candidate"
        app = output / "en-croissant.app"
        app.mkdir(parents=True)
        (app / "fixture").write_text("bundle fixture")
        bundle = {"app": manage.app_manifest(app), "executable_sha256": "fixture", "signing": "ad-hoc", "notarized": False}
        archive = output / "candidate.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.write(app / "fixture", "en-croissant.app/fixture")
        steps = []
        for name, command in manage.command_recipe():
            log = output / f"{name}.log"
            log.write_text("\n".join(f"test chess::lifecycle_tests::{name} ... ok" for name in names))
            steps.append({"name": name, "command": command, "exit_code": 0, "log": log.name, "sha256": manage.digest(log)})
        receipt = {"kind": "unpublished-candidate", "published": False, "installed": False, "manual_gates": manage.MANUAL_GATES.copy(), "distribution": manage.FEATURE, "version": "0.16.1-fork.1", "target": "aarch64-apple-darwin", **manage.source_identity(), "inputs": inputs, "tools": inputs, "checks": steps, "bundle": bundle, "archive": {"path": archive.name, "sha256": manage.digest(archive)}}
        path = output / "receipt.json"
        manage.write_json(path, receipt)
        original_run = manage.run
        def fake_extract(args, cwd=None, env=None):
            if args[0] == "ditto":
                with zipfile.ZipFile(args[-2]) as zipped:
                    zipped.extractall(args[-1])
                return ""
            return original_run(args, cwd, env)
        def fake_signature(app_path, version):
            return {**bundle, "app": manage.app_manifest(app_path)}
        with patch.object(manage, "run", side_effect=fake_extract), patch.object(manage, "validate_distribution", return_value=receipt["version"]), patch.object(manage, "verify_app", side_effect=fake_signature):
            manage.verify(path)
            wrong = json.loads(json.dumps(receipt))
            wrong["checks"][-1]["command"].remove("maintained-fork")
            manage.write_json(path, wrong)
            with self.assertRaisesRegex(ValueError, "command differs"):
                manage.verify(path)
            manage.write_json(path, receipt)
            log = output / "native-tests.log"
            original = log.read_text()
            log.write_text("changed log")
            with self.assertRaisesRegex(ValueError, "modified validation log"):
                manage.verify(path)
            log.write_text(original)
            content = archive.read_bytes()
            archive.write_bytes(content + b"changed")
            with self.assertRaisesRegex(ValueError, "Archive digest"):
                manage.verify(path)
            archive.write_bytes(content)
            self.write("pnpm-lock.yaml", "changed lock")
            with self.assertRaisesRegex(ValueError, "clean tracked"):
                manage.verify(path)

    def test_drift_clean_preserves_worktree_and_records_comparison(self):
        output = self.root / "scripts/fork/out/drift.json"
        manage.drift(output, self.base)
        report = manage.read_json(output)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["upstream_changed_paths"], [])
        self.assertEqual(report["merge_tree_exit_code"], 0)
        manage.clean_source()


class BundleFixture(unittest.TestCase):
    def test_manifest_detects_content_mode_and_link_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Example.app"
            app.mkdir()
            file = app / "binary"
            file.write_bytes(b"executable")
            before = manage.app_manifest(app)
            file.write_bytes(b"changed")
            self.assertNotEqual(before, manage.app_manifest(app))
            before = manage.app_manifest(app)
            file.chmod(0o755)
            self.assertNotEqual(before, manage.app_manifest(app))
            (app / "alias").symlink_to("binary")
            self.assertEqual(manage.app_manifest(app)["entries"][0]["target"], "binary")
            (app / "escape").symlink_to("../outside")
            with self.assertRaisesRegex(ValueError, "escapes"):
                manage.app_manifest(app)

    def test_bundled_extension_must_match_input_not_just_receipt_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Example.app"
            extension = app / "Contents/Resources/aixchess.duckdb_extension"
            extension.parent.mkdir(parents=True)
            extension.write_bytes(b"verified extension")
            pinned = {"size": extension.stat().st_size, "sha256": manage.digest(extension)}
            manage.validate_bundled_extension(app, pinned)
            extension.write_bytes(b"tampered extension")
            with self.assertRaisesRegex(ValueError, "Bundled AIX"):
                manage.validate_bundled_extension(app, pinned)

    def test_receipt_paths_cannot_escape_artifact_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                manage.safe_artifact(Path(directory), "../../outside")
            self.assertEqual(manage.safe_artifact(Path(directory), "receipt.json"), Path(directory) / "receipt.json")

    def test_pinned_extension_mismatch_is_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(manage, "ROOT", Path(directory)):
            file = Path(directory) / "aixchess.duckdb_extension"
            file.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "differs"):
                manage.pinned_extension({"size": 5, "sha256": "wrong"})
            self.assertEqual(file.read_bytes(), b"wrong")


class RecipeFixture(unittest.TestCase):
    def test_missing_reordered_duplicate_or_altered_commands_are_rejected(self):
        steps = [{"name": name, "command": command} for name, command in manage.command_recipe()]
        manage.validate_recipe(steps)
        for changed in (steps[:-1], steps[::-1], steps + [steps[-1]]):
            with self.subTest(names=[s["name"] for s in changed]):
                with self.assertRaisesRegex(ValueError, "recipe order"):
                    manage.validate_recipe(changed)
        changes = [
            ("native-build", lambda command: command.remove(manage.FEATURE)),
            ("native-build", lambda command: command.remove(manage.OVERLAY)),
            ("native-tests", lambda command: command.insert(-2, "engine_lifecycle")),
            ("frontend-build", lambda command: command.append("--mode=upstream")),
        ]
        for name, mutate in changes:
            changed = json.loads(json.dumps(steps))
            mutate(next(s["command"] for s in changed if s["name"] == name))
            with self.subTest(step=name):
                with self.assertRaisesRegex(ValueError, "command differs"):
                    manage.validate_recipe(changed)
        del steps[-1]["command"]
        with self.assertRaisesRegex(ValueError, "command differs"):
            manage.validate_recipe(steps)

    def test_old_bundle_is_preserved_but_cannot_be_mistaken_for_new_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            built = root / "target/release/bundle/macos/en-croissant.app"
            built.mkdir(parents=True)
            (built / "binary").write_text("old build")
            output = root / "candidate"
            output.mkdir()
            manage.stage_previous_bundle(built, output)
            self.assertFalse(built.exists())
            self.assertEqual((output / "previous-build.app/binary").read_text(), "old build")
            # A redirected build writes elsewhere; expected path remains absent.
            redirected = root / "target/arm64/release/bundle/macos/en-croissant.app"
            redirected.mkdir(parents=True)
            self.assertFalse(built.exists())

    def test_command_line_tools_receipt_retains_xcode_error_without_failing(self):
        result = subprocess.CompletedProcess(["xcodebuild", "-version"], 1, "", "CommandLineTools selected")
        with patch.object(manage.subprocess, "run", return_value=result), patch.object(manage, "run", side_effect=["/Library/Developer/CommandLineTools", "26.5"]):
            tools = manage.developer_tools()
        self.assertEqual(tools["sdk"], "26.5")
        self.assertEqual(tools["xcodebuild"]["exit_code"], 1)
        self.assertIn("CommandLineTools", tools["xcodebuild"]["stderr"])


class DistributionFixture(unittest.TestCase):
    def test_distribution_contract_rejects_updater_identity_and_env_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            (root / "src-tauri").mkdir()
            base = {"identifier": "org.encroissant.app", "bundle": {"macOS": {"signingIdentity": "-"}}}
            overlay = {"version": "0.16.1-fork.1", "bundle": {"createUpdaterArtifacts": False}, "plugins": {"updater": {"endpoints": []}}}
            manage.write_json(root / "src-tauri/tauri.conf.json", base)
            manage.write_json(root / manage.OVERLAY, overlay)
            self.assertEqual(manage.validate_distribution(root), "0.16.1-fork.1")
            with patch.dict(os.environ, {"VITE_EN_CROISSANT_DISTRIBUTION": "upstream"}):
                with self.assertRaisesRegex(ValueError, "Conflicting"):
                    manage.validate_distribution(root)
            with patch.dict(os.environ, {"TAURI_SIGNING_PRIVATE_KEY": "fixture"}):
                with self.assertRaisesRegex(ValueError, "not allowed"):
                    manage.validate_distribution(root)
            overlay["plugins"]["updater"]["endpoints"] = ["https://example.invalid/feed"]
            manage.write_json(root / manage.OVERLAY, overlay)
            with self.assertRaisesRegex(ValueError, "no updater"):
                manage.validate_distribution(root)


if __name__ == "__main__":
    unittest.main()
