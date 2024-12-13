import unittest
from agent import DictCmdLineOpts

class TestAgentTools(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_single_letter_has_single_dash(self):
        o = DictCmdLineOpts({"e" : None})
        self.assertEqual("-e", o.as_string())

    def test_multi_letter_has_two_dash(self):
        o = DictCmdLineOpts({"foo" : None})
        self.assertEqual("--foo", o.as_string())

    def test_single_letter_as_list(self):
        o = DictCmdLineOpts({"f" : "bar"})
        self.assertEqual("-f bar", " ".join(o.as_args()))

    def test_multi_letter_as_list(self):
        o = DictCmdLineOpts({"foo" : "bar"})
        self.assertEqual("--foo bar", " ".join(o.as_args()))

    def test_single_letter_with_str_arg(self):
        o = DictCmdLineOpts({"f" : "bar"})
        self.assertEqual("-f bar", o.as_string())

    def test_multi_letter_with_str_arg(self):
        o = DictCmdLineOpts({"foo" : "bar"})
        self.assertEqual("--foo bar", o.as_string())

    def test_single_letter_non_str_arg_skipped(self):
        o = DictCmdLineOpts({"f" : ["bar"]})
        self.assertLessEqual(len(o.as_string()), 0)

    def test_multi_letter_non_str_arg_skipped(self):
        o = DictCmdLineOpts({"foo" : ["bar"]})
        self.assertLessEqual(len(o.as_string()), 0)

    def test_zero_len_arg(self):
        o = DictCmdLineOpts({"" : "bar"})
        self.assertLessEqual(len(o.as_string()), 0)

if __name__ == '__main__':
    unittest.main()

