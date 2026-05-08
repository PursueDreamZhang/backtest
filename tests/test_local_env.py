import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from local_env import load_local_env


class LocalEnvTests(unittest.TestCase):
    def test_should_load_tushare_token_from_config_local_env(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "config" / "local.env"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("TUSHARE_TOKEN=test-token\n", encoding="utf-8")

            old_token = os.environ.pop("TUSHARE_TOKEN", None)
            try:
                loaded = load_local_env(env_path)
                self.assertEqual(loaded["TUSHARE_TOKEN"], "test-token")
                self.assertEqual(os.environ["TUSHARE_TOKEN"], "test-token")
            finally:
                if old_token is None:
                    os.environ.pop("TUSHARE_TOKEN", None)
                else:
                    os.environ["TUSHARE_TOKEN"] = old_token

    def test_should_not_override_existing_environment_variable(self):
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / "config" / "local.env"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("TUSHARE_TOKEN=file-token\n", encoding="utf-8")

            old_token = os.environ.get("TUSHARE_TOKEN")
            os.environ["TUSHARE_TOKEN"] = "env-token"
            try:
                loaded = load_local_env(env_path)
                self.assertEqual(loaded["TUSHARE_TOKEN"], "file-token")
                self.assertEqual(os.environ["TUSHARE_TOKEN"], "env-token")
            finally:
                if old_token is None:
                    os.environ.pop("TUSHARE_TOKEN", None)
                else:
                    os.environ["TUSHARE_TOKEN"] = old_token
