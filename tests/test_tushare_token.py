import os
import unittest

from data.tushare_source import TushareDataSource


class TestTushareToken(unittest.TestCase):
    def test_resolve_token_from_local_env(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        config_dir = os.path.join(project_root, 'config')
        local_env = os.path.join(config_dir, 'local.env')
        backup_file = None

        if os.path.exists(local_env):
            backup_file = local_env + '.bak_test'
            os.replace(local_env, backup_file)

        old_env = os.environ.get('TUSHARE_TOKEN')
        os.environ.pop('TUSHARE_TOKEN', None)

        try:
            os.makedirs(config_dir, exist_ok=True)
            with open(local_env, 'w', encoding='utf-8') as f:
                f.write('TUSHARE_TOKEN=test-token-123\n')

            token = TushareDataSource()._resolve_token()
            self.assertEqual(token, 'test-token-123')
        finally:
            if os.path.exists(local_env):
                os.remove(local_env)
            if backup_file and os.path.exists(backup_file):
                os.replace(backup_file, local_env)

            if old_env is None:
                os.environ.pop('TUSHARE_TOKEN', None)
            else:
                os.environ['TUSHARE_TOKEN'] = old_env


if __name__ == '__main__':
    unittest.main()
