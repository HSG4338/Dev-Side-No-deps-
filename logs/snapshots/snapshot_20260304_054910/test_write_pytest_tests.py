import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestWritePytestTests(unittest.TestCase):
    def test_import(self):
        mod = importlib.import_module("write_pytest_tests")
        self.assertIsNotNone(mod)
    def test_main_exists(self):
        mod = importlib.import_module("write_pytest_tests")
        self.assertTrue(hasattr(mod, "main"))

if __name__ == "__main__":
    unittest.main()
