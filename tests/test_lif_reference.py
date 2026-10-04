import unittest

from benchmarks.lif import python_reference


class LifReferenceTests(unittest.TestCase):
    def test_no_spikes_at_zero_steps(self):
        spikes, total = python_reference(10, 0)
        self.assertEqual((spikes, total), (0, 0.0))

    def test_reproducible(self):
        self.assertEqual(python_reference(32, 100), python_reference(32, 100))
        self.assertGreater(python_reference(32, 100)[0], 0)


if __name__ == "__main__":
    unittest.main()
