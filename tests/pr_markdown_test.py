import unittest
from workflows.pr import PullRequestDecoration


class TestPRMarkdown(unittest.TestCase):

    __test_good_md = [
        PullRequestDecoration._PullRequestDecoration__header_begin,
        PullRequestDecoration._PullRequestDecoration__cx_embed_header_img,
        PullRequestDecoration._PullRequestDecoration__header_end,
        PullRequestDecoration._PullRequestDecoration__annotation_begin,
        "annotation",
        PullRequestDecoration._PullRequestDecoration__annotation_end,
        PullRequestDecoration._PullRequestDecoration__body_begin,
        "body",
        PullRequestDecoration._PullRequestDecoration__body_end,
    ]

    __test_empty_md = [
        PullRequestDecoration._PullRequestDecoration__header_begin,
        PullRequestDecoration._PullRequestDecoration__cx_embed_header_img,
        PullRequestDecoration._PullRequestDecoration__header_end,
        PullRequestDecoration._PullRequestDecoration__annotation_begin,
        PullRequestDecoration._PullRequestDecoration__annotation_end,
        PullRequestDecoration._PullRequestDecoration__body_begin,
        PullRequestDecoration._PullRequestDecoration__body_end,
    ]

    __test_bad_md = [
        "foo",
        "bar",
        "baz"
    ]

    def test_canary(self):
        self.assertTrue(True)

    
    def test_parse_good_markdown(self):
        left = "\n".join(TestPRMarkdown.__test_good_md)
        right = PullRequestDecoration.from_markdown("\n".join(TestPRMarkdown.__test_good_md)).content
        self.assertEqual(left, right)

    def test_parse_bad_markdown(self):
        left = "\n".join(TestPRMarkdown.__test_empty_md)
        right = PullRequestDecoration.from_markdown("\n".join(TestPRMarkdown.__test_bad_md)).content
        self.assertEqual(left, right)



if __name__ == '__main__':
    unittest.main()

