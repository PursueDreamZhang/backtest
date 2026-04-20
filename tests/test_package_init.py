import importlib.util
import pathlib
import unittest


class TestPackageInit(unittest.TestCase):
    def test_should_support_direct_import_for_pytest_collection(self):
        init_path = pathlib.Path(__file__).resolve().parent.parent / '__init__.py'
        spec = importlib.util.spec_from_file_location('__init__', init_path)
        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

        self.assertEqual(module.__version__, '0.1.0')
        self.assertTrue(hasattr(module, 'BaseStrategy'))
        self.assertTrue(hasattr(module, 'Signal'))


if __name__ == '__main__':
    unittest.main()
