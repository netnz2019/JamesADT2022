import unittest
import render


class TestConvertCoords(unittest.TestCase):
    def test_convert_coords(self):
        """
        Test that the convert_coords function is mathematically correct
        """
        # Test data and expected results in nested list
        data = [[(0, 0), (960, 0)], [(0, 1000), (93, 499)], [(1000, 1000), (960, 999)], [(1000, 0), (1826, 499)]]
        for test_data in data:  # run several tests
            result = render.convert_coords(test_data[0][0], test_data[0][1])
            self.assertEqual(result, test_data[1])


if __name__ == '__main__':
    unittest.main()
