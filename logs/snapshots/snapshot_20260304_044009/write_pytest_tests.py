"""CLI calculator: add, subtract, multiply, divide."""
import sys

def add(a, b): return a + b
def subtract(a, b): return a - b
def multiply(a, b): return a * b
def divide(a, b):
    if b == 0: raise ValueError("Division by zero")
    return a / b

OPERATIONS = {"add": add, "+": add, "subtract": subtract, "-": subtract,
              "multiply": multiply, "*": multiply, "divide": divide, "/": divide}

def calculate(op, a, b):
    if op not in OPERATIONS:
        raise ValueError(f"Unknown operation: {op!r}. Use: add, subtract, multiply, divide")
    return OPERATIONS[op](a, b)

def main():
    args = sys.argv[1:]
    if len(args) == 3:
        try: print(calculate(args[0], float(args[1]), float(args[2])))
        except ValueError as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    else:
        print("Calculator — type 'quit' to exit. Usage: op a b")
        while True:
            try: line = input("> ").strip()
            except (EOFError, KeyboardInterrupt): break
            if line.lower() in ("quit", "exit"): break
            parts = line.split()
            if len(parts) != 3: print("Usage: op a b  (e.g. add 3 5)"); continue
            try: print(calculate(parts[0], float(parts[1]), float(parts[2])))
            except ValueError as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()