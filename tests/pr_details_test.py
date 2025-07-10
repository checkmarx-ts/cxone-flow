import unittest
from workflows.pr import SortedDetailRows, ResultSeverity


class TestDetailRow(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_row_order(self):
        row = str(SortedDetailRows.DetailRow(ResultSeverity.CRITICAL, ["foo", "bar"], foo="1", bar="2"))
        self.assertEqual(row, "| 1 | 2 |")

    def test_severity_match(self):
        self.assertEqual(ResultSeverity.CRITICAL, SortedDetailRows.DetailRow(ResultSeverity.CRITICAL, ["foo", "bar"], foo="1", bar="2").severity)

    def test_row_order_by_kwarg(self):
        row = str(SortedDetailRows.DetailRow(ResultSeverity.CRITICAL, ["foo", "bar"], bar="2", foo="1"))
        self.assertEqual(row, "| 1 | 2 |")

    def test_row_order_missing_arg(self):
        try:
            str(SortedDetailRows.DetailRow(ResultSeverity.CRITICAL, ["foo", "bar"], bar="2"))
            self.fail()
        except KeyError:
            self.assertTrue(True)

class TestSortedDetailRows(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_sort_by_severity(self):
        rows = SortedDetailRows(["foo"], lambda x: x.severity_rank_key)
        rows.add_row(ResultSeverity.INFO, foo="0", bar="1")
        rows.add_row(ResultSeverity.LOW, foo="1", bar="1")
        rows.add_row(ResultSeverity.MEDIUM, foo="2", bar="1")
        rows.add_row(ResultSeverity.HIGH, foo="3", bar="1")
        rows.add_row(ResultSeverity.CRITICAL, foo="4", bar="2")
        self.assertEqual(str(rows), "| 4 |\n| 3 |\n| 2 |\n| 1 |\n| 0 |")

    def test_sort_by_severity_composite_key(self):
        rows = SortedDetailRows(["foo"], lambda x: x.severity_rank_key + x['foo'])
        rows.add_row(ResultSeverity.CRITICAL, foo="2", bar="2")
        rows.add_row(ResultSeverity.CRITICAL, foo="1", bar="2")
        rows.add_row(ResultSeverity.CRITICAL, foo="0", bar="2")
        self.assertEqual(str(rows), "| 0 |\n| 1 |\n| 2 |")

    def test_sort_by_severity_2xcomposite_key(self):
        rows = SortedDetailRows(["foo", "bar"], lambda x: x.severity_rank_key + x['foo'] + x['bar'])
        rows.add_row(ResultSeverity.HIGH, foo="a", bar="a")
        rows.add_row(ResultSeverity.CRITICAL, foo="a", bar="z")
        rows.add_row(ResultSeverity.CRITICAL, foo="a", bar="x")
        rows.add_row(ResultSeverity.CRITICAL, foo="b", bar="a")
        self.assertEqual(str(rows), "| a | x |\n| a | z |\n| b | a |\n| a | a |")

    def test_sort_by_severity_composite_key_with_other_cols(self):
        rows = SortedDetailRows(["foo", "bar"], lambda x: x.severity_rank_key + x['foo'])
        rows.add_row(ResultSeverity.CRITICAL, foo="2", bar="a")
        rows.add_row(ResultSeverity.CRITICAL, foo="1", bar="b")
        rows.add_row(ResultSeverity.CRITICAL, foo="0", bar="c")
        self.assertEqual(str(rows), "| 0 | c |\n| 1 | b |\n| 2 | a |")


if __name__ == '__main__':
    unittest.main()
