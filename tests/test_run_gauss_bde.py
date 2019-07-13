import unittest
import os
from nrel_tools.run_gauss_bde import main
from nrel_tools.common import diff_lines, silent_remove, capture_stdout, capture_stderr
import logging

# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
DISABLE_REMOVE = logger.isEnabledFor(logging.DEBUG)

__author__ = 'hmayes'

TEST_DIR = os.path.dirname(__file__)
MAIN_DIR = os.path.dirname(TEST_DIR)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
SUB_DATA_DIR = os.path.join(DATA_DIR, 'run_gauss_bde')

DEF_INI = os.path.join(SUB_DATA_DIR, 'run_gauss_bde.ini')
F1_15_14_OUT = os.path.join(SUB_DATA_DIR, 'pet_mono_1_tzvp_15_14_f1.com')


class TestRunGaussBDENoOut(unittest.TestCase):
    # These all test failure cases
    def testNoArgs(self):
        with capture_stderr(main, []) as output:
            self.assertTrue("WARNING:  Problems reading file: Could not read file" in output)
        with capture_stdout(main, []) as output:
            self.assertTrue("optional arguments" in output)

    def testHelp(self):
        test_input = ['-h']
        if logger.isEnabledFor(logging.DEBUG):
            main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertFalse(output)
        with capture_stdout(main, test_input) as output:
            self.assertTrue("optional arguments" in output)


# class TestRunGaussBDE(unittest.TestCase):
#     # These test/demonstrate different options
#     def testDefIni(self):
#         test_input = ["ethylrad", "-c", DEF_INI]
#         try:
#             main(test_input)
#         finally:
#             pass

