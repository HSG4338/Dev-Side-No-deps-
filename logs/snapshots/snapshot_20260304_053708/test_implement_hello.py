import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestImplementHello(unittest.TestCase):
    def test_import(self):
        mod = importlib.import_module("implement_hello")
        self.assertIsNotNone(mod)
    def test_main_exists(self):
        mod = importlib.import_module("implement_hello")
        self.assertTrue(hasattr(mod, "main"))

if __name__ == "__main__":
    unittest.main()
