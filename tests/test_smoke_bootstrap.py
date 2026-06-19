import unittest
import turingos
from turingos import errors

class TestBootstrap(unittest.TestCase):
    def test_version(self):
        self.assertTrue(turingos.__version__.startswith("1.0"))
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(errors.GuardReject, errors.RejectedAppend))
        self.assertTrue(issubclass(errors.RejectedAppend, errors.TuringOSError))

if __name__ == "__main__":
    unittest.main()
