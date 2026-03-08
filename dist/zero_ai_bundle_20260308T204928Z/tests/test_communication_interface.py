import unittest

from ai_from_scratch.communication_interface import (
    CHANNEL_HUMAN,
    CHANNEL_PHYSICAL,
    CHANNEL_SYSTEM,
    CHANNEL_UNKNOWN,
    classify_input_channel,
    execution_interface,
    goal_alignment,
    receive_input,
)


class CommunicationInterfaceTests(unittest.TestCase):
    def test_channel_classification(self) -> None:
        self.assertEqual(CHANNEL_SYSTEM, classify_input_channel("api: get status"))
        self.assertEqual(CHANNEL_PHYSICAL, classify_input_channel("sensor: cpu temp"))
        self.assertEqual(CHANNEL_HUMAN, classify_input_channel("please optimize storage"))
        self.assertEqual(CHANNEL_UNKNOWN, classify_input_channel("   "))

    def test_receive_input_normalizes_and_validates(self) -> None:
        packet = receive_input("   hello    world   ")
        self.assertTrue(packet.safe)
        self.assertEqual("hello world", packet.content)

        empty = receive_input("    ")
        self.assertFalse(empty.safe)
        self.assertEqual(CHANNEL_UNKNOWN, empty.channel)

    def test_goal_alignment_blocks_unsafe_goal(self) -> None:
        unsafe_packet = receive_input("delete all files now")
        align = goal_alignment(unsafe_packet)
        self.assertFalse(align["pass"])

        safe_packet = receive_input("optimize memory and scan status")
        align2 = goal_alignment(safe_packet)
        self.assertTrue(align2["pass"])

    def test_execution_interface_routes_safe_output(self) -> None:
        routed = execution_interface("done", CHANNEL_HUMAN)
        self.assertTrue(routed["allowed"])
        self.assertEqual("done", routed["safe_output"])

        blocked = execution_interface("done", CHANNEL_UNKNOWN)
        self.assertFalse(blocked["allowed"])
        self.assertEqual("", blocked["safe_output"])


if __name__ == "__main__":
    unittest.main()
