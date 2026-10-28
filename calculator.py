class Calculator:
    # Additionne deux nombres
    def add(self, a, b):
        return a + b

    # Soustrait deux nombres
    def subtract(self, a, b):
        return a - b


# Crée une instance de Calculator
calc = Calculator()

# Affiche les résultats
print("Addition :", calc.add(10, 5))
print("Soustraction :", calc.subtract(10, 5))