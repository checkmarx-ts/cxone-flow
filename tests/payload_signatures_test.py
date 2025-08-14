import unittest
from api_utils import verify_signature, gen_signature_header, gen_signature_hash

class TestPayloadSignatures(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_sha256_matches(self):
        payload = b'{"eventKey":"repo:refs_changed","date":"2024-04-17T19:35:25+0000","actor":{"name":"admin","emailAddress":"a@a.com","active":true,"displayName":"Admin Person","id":3,"slug":"admin","type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/users/admin"}]}},"repository":{"slug":"simply_vulnerable_react","id":1,"name":"simply_vulnerable_react","hierarchyId":"cb6e391e5d6e875a0ef6","scmId":"git","state":"AVAILABLE","statusMessage":"Available","forkable":true,"project":{"key":"PA","id":1,"name":"ProjectA","public":false,"type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/projects/PA"}]}},"public":false,"archived":false,"links":{"clone":[{"href":"http://bbdc.cxsecure.nl:7990/scm/pa/simply_vulnerable_react.git","name":"http"},{"href":"ssh://git@bbdc.cxsecure.nl:7999/pa/simply_vulnerable_react.git","name":"ssh"}],"self":[{"href":"http://bbdc.cxsecure.nl:7990/projects/PA/repos/simply_vulnerable_react/browse"}]}},"changes":[{"ref":{"id":"refs/heads/master","displayId":"master","type":"BRANCH"},"refId":"refs/heads/master","fromHash":"33365d7d90e7939ce41b40f29851621f3780fbb1","toHash":"2f46e2fa1a1a067bd1b87e7aa16d7e0caf90d801","type":"UPDATE"}],"commits":[{"id":"2f46e2fa1a1a067bd1b87e7aa16d7e0caf90d801","displayId":"2f46e2fa1a1","author":{"name":"admin","emailAddress":"a@a.com","active":true,"displayName":"Admin Person","id":3,"slug":"admin","type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/users/admin"}]}},"authorTimestamp":1713382525000,"committer":{"name":"admin","emailAddress":"a@a.com","active":true,"displayName":"Admin Person","id":3,"slug":"admin","type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/users/admin"}]}},"committerTimestamp":1713382525000,"message":"README.md edited online with Bitbucket","parents":[{"id":"33365d7d90e7939ce41b40f29851621f3780fbb1","displayId":"33365d7d90e"}]}],"toCommit":{"id":"2f46e2fa1a1a067bd1b87e7aa16d7e0caf90d801","displayId":"2f46e2fa1a1","author":{"name":"admin","emailAddress":"a@a.com","active":true,"displayName":"Admin Person","id":3,"slug":"admin","type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/users/admin"}]}},"authorTimestamp":1713382525000,"committer":{"name":"admin","emailAddress":"a@a.com","active":true,"displayName":"Admin Person","id":3,"slug":"admin","type":"NORMAL","links":{"self":[{"href":"http://bbdc.cxsecure.nl:7990/users/admin"}]}},"committerTimestamp":1713382525000,"message":"README.md edited online with Bitbucket","parents":[{"id":"33365d7d90e7939ce41b40f29851621f3780fbb1","displayId":"33365d7d90e","author":{"name":"Admin Person","emailAddress":"a@a.com"},"authorTimestamp":1713382292000,"committer":{"name":"Admin Person","emailAddress":"a@a.com"},"committerTimestamp":1713382292000,"message":"README.md edited online with Bitbucket","parents":[{"id":"b39c10e6e842846949628ed72f098d76ee773b31","displayId":"b39c10e6e84"}]}]}}'
        signature_header = "sha256=49435c7bac158ed23f5f5edbb7b6937be9a87fecebe1707d6f498227f79a9074"
        self.assertTrue(verify_signature(signature_header, "password", payload))

    def test_header_uses_hash_func(self):
        body = b"abc"
        secret = "Xyz123!"
        hash = gen_signature_hash("sha256", secret, body)
        alg, generated_hash = gen_signature_header(secret, body)
        self.assertTrue(generated_hash == hash)

    def test_generated_header_verifies(self):
        body = b"abc"
        secret = "Xyz123!"
        alg, hash = gen_signature_header(secret, body)
        self.assertTrue(verify_signature(f"{alg}={hash}", secret, body))


if __name__ == '__main__':
    unittest.main()

