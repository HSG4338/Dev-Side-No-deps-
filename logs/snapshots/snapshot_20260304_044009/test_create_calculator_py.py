import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import create_calculator_py

class TestCreateCalculatorPy(unittest.TestCase):
    def test_add(self):
        self.assertEqual(create_calculator_py.add(3, 5), 8)
    def test_subtract(self):
        self.assertEqual(create_calculator_py.subtract(10, 4), 6)
    def test_multiply(self):
        self.assertEqual(create_calculator_py.multiply(6, 7), 42)
    def test_divide(self):
        self.assertAlmostEqual(create_calculator_py.divide(10, 2), 5.0)
    def test_divide_by_zero(self):
        with self.assertRaises((ValueError, ZeroDivisionError)):
            create_calculator_py.divide(1, 0)
    def test_calculate_add(self):
        self.assertEqual(create_calculator_py.calculate("add", 2, 3), 5)
    def test_calculate_unknown(self):
        with self.assertRaises((ValueError, KeyError)):
            create_calculator_py.calculate("modulo", 5, 3)

if __name__ == "__main__":
    unittest.main()
