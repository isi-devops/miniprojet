import unittest
from calculator import Calculator


class TestCalculator(unittest.TestCase):

    # Initialise la calculatrice avant chaque test
    def setUp(self):
        self.calculator = Calculator()

    # Teste l'addition
    def test_add(self):
        self.assertEqual(self.calculator.add(2, 3), 5)

    # Teste la soustraction
    def test_subtract(self):
        self.assertEqual(self.calculator.subtract(5, 3), 2)


# Lance les tests si le fichier est execute directement
if __name__ == "__main__":
    unittest.main()