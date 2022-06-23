import unittest
from render import convert_coords


class TestConvertMethod(unittest.TestCase):

    def test_convert_offsets(self):
        self.assertEqual(convert_coords(0, 0), 'FOO')