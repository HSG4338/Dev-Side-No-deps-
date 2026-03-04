import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import write_pytest_tests

class TestWritePytestTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(write_pytest_tests.add(3, 5), 8)
    def test_subtract(self):
        self.assertEqual(write_pytest_tests.subtract(10, 4), 6)
    def test_multiply(self):
        self.assertEqual(write_pytest_tests.multiply(6, 7), 42)
    def test_divide(self):
        self.assertAlmostEqual(write_pytest_tests.divide(10, 2), 5.0)
    def test_divide_by_zero(self):
        with self.assertRaises((ValueError, ZeroDivisionError)):
            write_pytest_tests.divide(1, 0)
    def test_calculate_add(self):
        self.assertEqual(write_pytest_tests.calculate("add", 2, 3), 5)
    def test_calculate_unknown(self):
        with self.assertRaises((ValueError, KeyError)):
            write_pytest_tests.calculate("modulo", 5, 3)

if __name__ == "__main__":
    unittest.main()
