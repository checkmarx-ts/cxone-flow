import unittest
from workflows.messaging.base_message import StampedMessage


class TestMessageSerialization(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_timestamp_binary_serialization(self):
        msg = StampedMessage.factory()
        serialized = msg.to_binary()
        deserialized = StampedMessage.from_binary(serialized)
        self.assertEqual(deserialized.timestamp, msg.timestamp)



if __name__ == '__main__':
    unittest.main()

