import unittest
import os
from nrel_tools.gausslog_unique import main
from common_wrangler.common import capture_stdout, capture_stderr
import logging

# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
DISABLE_REMOVE = logger.isEnabledFor(logging.DEBUG)

__author__ = 'hmayes'

TEST_DIR = os.path.dirname(__file__)
MAIN_DIR = os.path.dirname(TEST_DIR)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
SUB_DATA_DIR = os.path.join(DATA_DIR, 'gausslog_unique')

LOG_LIST = os.path.join(SUB_DATA_DIR, 'list.txt')

HEADER = 'File,Convergence,Energy,Enthalpy\n'
ALPHA_FIRST = 'lme2acetoxprpnt_ts3_ircf_opt.log,7.5369,-535.578433967,-535.403311\n'
MISSING_FREQ = 'lme2acetoxprpnt_ts3_ircf_opt_no_freq.log,0.9367,-535.578433967,None\n'
ENERGY_FIRST = 'lme2acetoxypropionate_25_t.log,0.1303,-535.578442535,-535.403293\n'

EMPTY_LIST = os.path.join(SUB_DATA_DIR, 'empty_list.txt')
LIST_NO_FREQ = os.path.join(SUB_DATA_DIR, 'list_no_freq.txt')
MISSING_FILE_LIST = os.path.join(SUB_DATA_DIR, 'list_with_missing_files.txt')
TWO_MOL_LIST = os.path.join(SUB_DATA_DIR, 'list_two_molecules.txt')


class TestGausslogUniqueNoOut(unittest.TestCase):
    # These all test failure cases
    def testNoArgs(self):
        test_input = []
        # main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Problems reading file" in output)

        # with capture_stderr(main, test_input) as output:
        #     self.assertTrue("No files to process" in output)
    def testNoFiles(self):
        test_input = ["-l", EMPTY_LIST]
        # main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("This program expects at least two files" in output)

    def testMissingFiles(self):
        test_input = ["-l", MISSING_FILE_LIST]
        # main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Could not find the following file" in output)

    def testHelp(self):
        test_input = ['-h']
        if logger.isEnabledFor(logging.DEBUG):
            main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertFalse(output)
        with capture_stdout(main, test_input) as output:
            self.assertTrue("optional arguments" in output)


class TestGausslogUnique(unittest.TestCase):
    # These test/demonstrate different options
    def testStandard(self):
        test_input = ["-l", LOG_LIST]
        good_output = ''.join([HEADER, ALPHA_FIRST, ENERGY_FIRST])
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
        with capture_stderr(main, test_input) as output:
            self.assertTrue('Check convergence' in output)

    # These test/demonstrate different options
    def testSortByEnergy(self):
        test_input = ["-l", LOG_LIST, "-e"]
        good_output = ''.join([HEADER, ENERGY_FIRST, ALPHA_FIRST])
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
        with capture_stderr(main, test_input) as output:
            self.assertTrue('Check convergence' in output)

    def testSortByEnthalpy(self):
        test_input = ["-l", LOG_LIST, '-n']
        good_output = ''.join([HEADER, ALPHA_FIRST, ENERGY_FIRST])
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
        with capture_stderr(main, test_input) as output:
            self.assertTrue('Check convergence' in output)

    def testNoFreq(self):
        test_input = ["-l", LIST_NO_FREQ, "-n"]
        good_output = ''.join([HEADER, ENERGY_FIRST, MISSING_FREQ])
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
        with capture_stderr(main, test_input) as output:
            self.assertFalse('Check convergence' in output)

    def testTwoMolecules(self):
        pet_843 = 'pet_mono_843_tzvp.log,1.4694,-917.071861101,-916.796704\n'
        pet_1 = 'pet_mono_1_tzvp.log,0.8478,-917.069490509,-916.794649\n'
        test_input = ["-l", TWO_MOL_LIST, "-n"]
        good_output = ''.join([HEADER, pet_843, pet_1, ALPHA_FIRST, ENERGY_FIRST])
        main(test_input)
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
        with capture_stderr(main, test_input) as output:
            self.assertTrue('pet_mono_843_tzvp.log' in output)
