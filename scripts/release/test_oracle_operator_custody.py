"""Owner-TTY prerequisite tests use only disposable invented credentials."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import oracle_operator_custody as custody
import oracle_robot as r


class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            dir="/private/tmp" if Path("/private/tmp").exists() else None
        )
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.root.chmod(0o700)
        self.candidate = "a" * 40
        self.password = "synthetic-existing-operator-only"
        salt = "b" * 32
        self.encoded = (
            "scrypt$"
            + salt
            + "$"
            + hashlib.scrypt(
                self.password.encode(),
                salt=bytes.fromhex(salt),
                n=16384,
                r=8,
                p=1,
                dklen=64,
            ).hex()
        )
        self.config = {
            env: {
                "ROBOT_OPERATOR_NAME": "existing-operator",
                "ROBOT_OPERATOR_PASSWORD_HASH": self.encoded,
                "ROBOT_ACTUATION_ENABLED": "false",
                "ROBOT_STORAGE_MODE": "turso",
            }
            for env in ["staging", "production"]
        }
        self.env = {env: self.root / (env + ".env") for env in self.config}
        for env, path in self.env.items():
            path.write_text(
                "".join(k + "=" + v + "\n" for k, v in self.config[env].items())
            )
            path.chmod(0o600)
        self.path = self.root / "runtime" / "robot-operator.json"
        self.plan = {"bindings": {"api": {"candidate_commit": self.candidate}}}
        for name, value in [("CUSTODY", self.path), ("ENV", self.env)]:
            mock = patch.object(r, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        self.pin = patch.object(r, "verify_toolchain")
        self.verifier = self.pin.start()
        self.addCleanup(self.pin.stop)
        mock = patch.object(r, "private", side_effect=lambda p, **kw: Path(p))
        mock.start()
        self.addCleanup(mock.stop)

    def test_frontend_mode_custody_uses_current_frontend_not_original_api_source(self):
        self.plan["release_component"] = "frontend"
        self.plan["bindings"]["frontend"] = {"candidate_commit": self.candidate}
        self.plan["bindings"]["api"] = {"candidate_commit": "c" * 40}
        result = custody.collect(
            self.plan, self.candidate, prompt=lambda _: self.password
        )
        self.assertEqual(result["candidate_commit"], self.candidate)
        self.verifier.assert_called_once_with(
            self.plan, self.plan["bindings"]["frontend"]
        )
        self.assertFalse(result["release_authority"])

    def test_unknown_component_mode_cannot_collect_credentials(self):
        self.plan["release_component"] = "other"
        with self.assertRaises(r.Refused):
            custody.collect(self.plan, self.candidate, prompt=lambda _: self.password)
        self.assertFalse(self.path.exists())

    def test_matches_real_existing_scrypt_without_changing_account(self):
        self.assertTrue(custody.matches_password(self.password, self.encoded))
        self.assertFalse(custody.matches_password("wrong", self.encoded))
        self.assertFalse(
            custody.matches_password(self.password, "scrypt$bad$malformed")
        )
        self.assertFalse(
            custody.matches_password(
                self.password, "scrypt$" + "0" * 32 + "$" + "0" * 128
            )
        )

    def test_valid_hidden_collection_is_source_bound_and_never_authority(self):
        old = {env: r.sha(path) for env, path in self.env.items()}
        result = custody.collect(
            self.plan, self.candidate, prompt=lambda _: self.password
        )
        self.assertFalse(result["release_authority"])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual({env: r.sha(path) for env, path in self.env.items()}, old)
        value = r.read(self.path)
        self.assertEqual(value["candidate_commit"], self.candidate)
        self.assertLessEqual(
            r.dt.datetime.fromisoformat(value["expires_at"])
            - r.dt.datetime.fromisoformat(value["created_at"]),
            r.dt.timedelta(hours=1),
        )
        with self.assertRaises(r.Refused):
            custody.collect(self.plan, self.candidate, prompt=lambda _: self.password)

    def test_wrong_password_source_actuation_or_tool_pin_never_writes_custody(self):
        for password, candidate in [
            ("wrong", self.candidate),
            (self.password, "c" * 40),
        ]:
            with (
                self.subTest(
                    candidate=candidate, password_matches=password == self.password
                ),
                self.assertRaises(r.Refused),
            ):
                custody.collect(
                    self.plan, candidate, prompt=lambda _, current=password: current
                )
            self.assertFalse(self.path.exists())
        self.verifier.side_effect = r.Refused("UNREVIEWED_TOOL")
        with self.assertRaises(r.Refused):
            custody.collect(self.plan, self.candidate, prompt=lambda _: self.password)
        self.assertFalse(self.path.exists())

    def test_staging_device_token_must_match_existing_hash(self):
        with self.env["staging"].open("a") as stream:
            stream.write(
                "ROBOT_EDGE_DEVICE_ID=synthetic-fixture\nROBOT_EDGE_TOKEN_SHA256="
                + hashlib.sha256(b"owned-edge-only").hexdigest()
                + "\n"
            )
        answers = iter([self.password, "forged-device-token"])
        with self.assertRaises(r.Refused):
            custody.collect(self.plan, self.candidate, prompt=lambda _: next(answers))
        self.assertFalse(self.path.exists())

    def test_expired_temporary_custody_cannot_be_used_or_clear_a_fresh_file(self):
        custody.collect(self.plan, self.candidate, prompt=lambda _: self.password)
        with self.assertRaises(r.Refused):
            custody.clear_expired(self.candidate)
        value = r.read(self.path)
        value["expires_at"] = (r.now() - r.dt.timedelta(seconds=1)).isoformat()
        self.path.write_bytes(r.canonical(value))
        with self.assertRaises(r.Refused):
            r.credentials(
                {
                    "baseline_runtime_sha256": {
                        env: r.sha(path) for env, path in self.env.items()
                    }
                },
                {"candidate_commit": self.candidate},
            )
        result = custody.clear_expired(self.candidate)
        self.assertEqual(result["state"], "EXPIRED_TEMPORARY_CUSTODY_CLEARED")
        self.assertFalse(self.path.exists())
        self.assertTrue(all(path.exists() for path in self.env.values()))
