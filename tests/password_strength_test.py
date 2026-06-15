import unittest, string
from config.server.scmservice_factories import PasswordStrengthValidator

class TestPasswordStrength(unittest.TestCase):

      def setUp(self):
        self.__shared_secret_policy = PasswordStrengthValidator.from_names(
            length=20, uppercase=3, numbers=3, special=2)
        self.__valid_uppercase ="ABC"
        self.__valid_numbers = "321"
        self.__valid_special = "!("
        self.__remaining_length = 20 - len(self.__valid_uppercase + self.__valid_numbers + self.__valid_special)
        
      def test_combo_invalid_length(self):
        self.assertFalse(self.__shared_secret_policy.test(self.__valid_uppercase + self.__valid_numbers + self.__valid_special + "a" * (self.__remaining_length - 1)))

      def test_valid_order_1(self):
        self.assertTrue(self.__shared_secret_policy.test("a" * self.__remaining_length + self.__valid_uppercase + self.__valid_numbers + self.__valid_special))

      def test_valid_order_2(self):
        self.assertTrue(self.__shared_secret_policy.test(self.__valid_uppercase + "a" * self.__remaining_length  + self.__valid_numbers + self.__valid_special))

      def test_valid_order_3(self):
        self.assertTrue(self.__shared_secret_policy.test(self.__valid_uppercase + self.__valid_numbers + "a" * self.__remaining_length  + self.__valid_special))

      def test_valid_order_4(self):
        self.assertTrue(self.__shared_secret_policy.test(self.__valid_special + self.__valid_uppercase + self.__valid_numbers + "a" * self.__remaining_length))

      def test_canary(self):
        self.assertTrue(True)

      def test_under_length(self):
        val = PasswordStrengthValidator.from_names(length = 20)
        self.assertFalse(val.test("a" * 19))

      def test_exact_length(self):
        val = PasswordStrengthValidator.from_names(length = 20)
        self.assertTrue(val.test("a" * 20))

      def test_exceeds_length(self):
        val = PasswordStrengthValidator.from_names(length = 20)
        self.assertTrue(val.test("a" * 22))

      def test_under_length_uppercase(self):
        val = PasswordStrengthValidator.from_names(uppercase = 3)
        self.assertFalse(val.test("a" * 2 + "AB"))

      def test_exact_length_uppercase(self):
        val = PasswordStrengthValidator.from_names(uppercase = 3)
        self.assertTrue(val.test("a" * 20 + "B" * 3))

      def test_exceeds_length_uppercase(self):
        val = PasswordStrengthValidator.from_names(uppercase = 3)
        self.assertTrue(val.test("a" * 20 + "B" * 5))

      def test_under_length_numbers(self):
        val = PasswordStrengthValidator.from_names(numbers = 3)
        self.assertFalse(val.test("2" + "a" * 2 + "1"))

      def test_exact_length_numbers(self):
        val = PasswordStrengthValidator.from_names(numbers = 3)
        self.assertTrue(val.test("1" + "a" * 20 + "09"))

      def test_exceeds_length_numbers(self):
        val = PasswordStrengthValidator.from_names(numbers = 3)
        self.assertTrue(val.test("a" * 20 + "0123456789"))

      def test_under_length_special(self):
        val = PasswordStrengthValidator.from_names(special = 3)
        self.assertFalse(val.test("2" + "a" * 2 + "1"))

      def test_exact_length_special(self):
        val = PasswordStrengthValidator.from_names(special = 3)
        self.assertTrue(val.test("1" + "a" * 20 + string.punctuation[:-3]))

      def test_exceeds_length_special(self):
        val = PasswordStrengthValidator.from_names(special = 3)
        self.assertTrue(val.test("1" + "a" * 20 + string.punctuation))

if __name__ == '__main__':
    unittest.main()
