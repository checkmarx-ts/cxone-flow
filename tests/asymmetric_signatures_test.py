import unittest
from api_utils.signatures import AsymmetricSignatureSignerVerifier, AsymmetricSignatureVerifier
from workflows.messaging.base_message import StampedMessage

class TestAsymmetricSignatures(unittest.TestCase):

    __test_data = b'This is a test message'
    __test_data2 = b'This is the wrong test message'

    __priv_index = 0
    __pub_index = 1

    __key_pair_tuples = {
        "ec1" : ("test_data/ec-priv.1.pem", "test_data/ec-pub.1.pem"),
        "ec2" : ("test_data/ec-priv.2.pem", "test_data/ec-pub.2.pem"),
        "rsa1" : ("test_data/rsa-priv.1.pem", "test_data/rsa-pub.1.pem"),
        "rsa2" : ("test_data/rsa-priv.2.pem", "test_data/rsa-pub.2.pem")
    }

    @staticmethod
    def __load_key_data(filepath : str):
        with open(filepath, "rb") as keyfile:
            return keyfile.read()
        
    @staticmethod
    def __get_pub_priv_by_name(test_name : str):
        return TestAsymmetricSignatures.__load_key_data(TestAsymmetricSignatures.__key_pair_tuples[test_name][TestAsymmetricSignatures.__priv_index]), \
            TestAsymmetricSignatures.__load_key_data(TestAsymmetricSignatures.__key_pair_tuples[test_name][TestAsymmetricSignatures.__pub_index])

    def test_canary(self):
        self.assertTrue(True)

    def test_sig_from_private_success(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            msg = StampedMessage.factory()

            private, public = TestAsymmetricSignatures.__get_pub_priv_by_name(test)

            with self.subTest(f"{test} private only"):
                obj = AsymmetricSignatureSignerVerifier.from_private_key(private)

                try:
                    obj.verify(obj.sign(msg.to_binary()), msg.to_binary())
                    self.assertTrue(True)
                except:
                    self.assertTrue(False)

            with self.subTest(f"{test} private sign public verify"):
                signer = AsymmetricSignatureSignerVerifier.from_private_key(private)
                verifier = AsymmetricSignatureVerifier.from_public_key(public)

                try:
                    verifier.verify(signer.sign(msg.to_binary()), msg.to_binary())
                    self.assertTrue(True)
                except:
                    self.assertTrue(False)

    def test_sig_fail_from_private(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                private, _ = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                obj = AsymmetricSignatureSignerVerifier.from_private_key(private)

                try:
                    obj.verify(obj.sign(TestAsymmetricSignatures.__test_data), TestAsymmetricSignatures.__test_data2)
                    self.assertTrue(False)
                except:
                    self.assertTrue(True)

    def test_serialized_msg_sig_success(self):

        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                private,public_ = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                obj = AsymmetricSignatureSignerVerifier.from_private_key(private)

                try:
                    obj.verify(obj.sign(TestAsymmetricSignatures.__test_data), TestAsymmetricSignatures.__test_data)
                    self.assertTrue(True)
                except:
                    self.assertTrue(False)

    def test_sig_from_public_success(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                private, public = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                signer = AsymmetricSignatureSignerVerifier.from_private_key(private)

                verifier = AsymmetricSignatureVerifier.from_public_key(public)

                try:
                    verifier.verify(signer.sign(TestAsymmetricSignatures.__test_data), TestAsymmetricSignatures.__test_data)
                    self.assertTrue(True)
                except:
                    self.assertTrue(False)


    def test_sig_fail_from_public(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                private, public = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                signer = AsymmetricSignatureSignerVerifier.from_private_key(private)

                verifier = AsymmetricSignatureVerifier.from_public_key(public)

                try:
                    verifier.verify(signer.sign(TestAsymmetricSignatures.__test_data2), TestAsymmetricSignatures.__test_data)
                    self.assertTrue(False)
                except:
                    self.assertTrue(True)

    def test_with_none_private(self):
        try:
            AsymmetricSignatureSignerVerifier.from_private_key(None)
            self.assertTrue(False)
        except:
            self.assertTrue(True)

    def test_with_none_public(self):
        try:
            AsymmetricSignatureVerifier.from_public_key(None)
            self.assertTrue(False)
        except:
            self.assertTrue(True)

    def test_load_public_as_private(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                try:
                    _, public = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                    AsymmetricSignatureSignerVerifier.from_private_key(public)
                    self.assertTrue(False)
                except:
                    self.assertTrue(True)

    def test_load_private_as_public(self):
        for test in TestAsymmetricSignatures.__key_pair_tuples.keys():
            with self.subTest(test):
                try:
                    private, _ = TestAsymmetricSignatures.__get_pub_priv_by_name(test)
                    AsymmetricSignatureVerifier.from_public_key(private)
                    self.assertTrue(False)
                except:
                    self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()

