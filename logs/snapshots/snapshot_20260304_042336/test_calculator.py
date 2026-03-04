"""Tests for calculator.py — stdlib unittest only."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculator import add, subtract, multiply, divide, calculate

class TestCalculator(unittest.TestCase):
    def test_add(self):          self.assertEqual(add(3, 5), 8)
    def test_add_float(self):    self.assertAlmostEqual(add(1.1, 2.2), 3.3)
    def test_add_negative(self): self.assertEqual(add(-4, 6), 2)
    def test_subtract(self):     self.assertEqual(subtract(10, 4), 6)
    def test_subtract_neg(self): self.assertEqual(subtract(3, 10), -7)
    def test_multiply(self):     self.assertEqual(multiply(6, 7), 42)
    def test_multiply_zero(self):self.assertEqual(multiply(99, 0), 0)
    def test_multiply_float(self):self.assertAlmostEqual(multiply(2.5, 4.0), 10.0)
    def test_divide(self):       self.assertEqual(divide(10, 2), 5.0)
    def test_divide_float(self): self.assertAlmostEqual(divide(7, 2), 3.5)
    def test_divide_by_zero(self):
        with self.assertRaises(ValueError): divide(5, 0)
    def test_calc_add(self):     self.assertEqual(calculate("add",  1, 2), 3)
    def test_calc_plus(self):    self.assertEqual(calculate("+",    1, 2), 3)
    def test_calc_sub(self):     self.assertEqual(calculate("subtract", 10, 3), 7)
    def test_calc_minus(self):   self.assertEqual(calculate("-", 10, 3), 7)
    def test_calc_mul(self):     self.assertEqual(calculate("multiply", 4, 5), 20)
    def test_calc_star(self):    self.assertEqual(calculate("*", 4, 5), 20)
    def test_calc_div(self):     self.assertAlmostEqual(calculate("divide", 9, 3), 3.0)
    def test_calc_slash(self):   self.assertAlmostEqual(calculate("/", 9, 3), 3.0)
    def test_calc_unknown(self):
        with self.assertRaises(ValueError): calculate("modulo", 10, 3)

if __name__ == "__main__": unittest.main()
