import unittest
import os
from shutil import copyfile
from gaussian_wrangler.check_gauss import main
from common_wrangler.common import capture_stdout, capture_stderr, diff_lines, silent_remove
import logging

# logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
DISABLE_REMOVE = logger.isEnabledFor(logging.DEBUG)

__author__ = 'hmayes'

TEST_DIR = os.path.dirname(__file__)
MAIN_DIR = os.path.dirname(TEST_DIR)
DATA_DIR = os.path.join(TEST_DIR, 'test_data')
SUB_DATA_DIR = os.path.join(DATA_DIR, 'check_gauss')
ALT_DATA_DIR = os.path.join(DATA_DIR, 'gausslog_unique')

NORM_TERM_LOG = os.path.join(SUB_DATA_DIR, 'pet_mono_637_tzvp.tpl')
TEMP_NORM_TERM_LOG = os.path.join(SUB_DATA_DIR, 'pet_mono_637_tzvp.log')
FOR_HARTREE_DIR = os.path.join(MAIN_DIR, 'for_hartree')
MOVED_FILE = os.path.join(FOR_HARTREE_DIR, 'pet_mono_637_tzvp.log')
SINGLE_FILE = os.path.join(SUB_DATA_DIR, 'me2propprpnt_7.log')

GOOD_OUT = "The following files completed normally:\n" \
           "    tests/test_data/check_gauss/pet_mono_637_tzvp.log\n" \
           "The following files may have failed:\n" \
           "    tests/test_data/check_gauss/me2propprpnt_7.log\n" \
           "    tests/test_data/check_gauss/pet_mono_674_tzvp.log\n" \
           "    tests/test_data/check_gauss/pet_mono_819_tzvp.log\n" \
           "    tests/test_data/check_gauss/pet_mono_872_tzvp.log\n" \
           "The following files may still be running:\n" \
           "    tests/test_data/check_gauss/pet_mono_671_tzvp.log\n"

LIST_FILE = os.path.join(SUB_DATA_DIR, 'list.txt')
CONV_239_OUT = os.path.join(ALT_DATA_DIR, 'hexyl_acrylate_239_conv_steps.csv')
CONV_419_OUT = os.path.join(ALT_DATA_DIR, 'hexyl_acrylate_419_conv_steps.csv')
GOOD_CONV_239_OUT = os.path.join(ALT_DATA_DIR, 'hexyl_acrylate_239_conv_steps_good.csv')
GOOD_CONV_419_OUT = os.path.join(ALT_DATA_DIR, 'hexyl_acrylate_419_conv_steps_good.csv')

DIOXOLAN_OUT = os.path.join(SUB_DATA_DIR, 'dioxolan4ol_ts4_ts_conv_steps.csv')
GOOD_DIOXOLAN_OUT = os.path.join(SUB_DATA_DIR, 'dioxolan4ol_ts4_ts_conv_steps_good.csv')


class TestCheckGaussNoOut(unittest.TestCase):
    # These test failure cases that do not produce output files
    def testNoArgs(self):
        test_input = []
        # main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Could not find files" in output)
        silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)

    def testHelp(self):
        test_input = ['-h']
        if logger.isEnabledFor(logging.DEBUG):
            main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertFalse(output)
        with capture_stdout(main, test_input) as output:
            self.assertTrue("optional arguments" in output)
        silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)

    def testWrongKey(self):
        test_input = ['-ghost']
        if logger.isEnabledFor(logging.DEBUG):
            main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("unrecognized arguments" in output)
        with capture_stdout(main, test_input) as output:
            self.assertTrue("optional arguments" in output)
        silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)

    def testWrongDir(self):
        test_input = ["-d", "ghost"]
        if logger.isEnabledFor(logging.DEBUG):
            main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Could not find" in output)
        silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)

    def testConflictingOptions(self):
        test_input = ["-s", "-z"]
        # main(test_input)
        # if logger.isEnabledFor(logging.DEBUG):
        #     main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Choose either" in output)
        silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)

    def testNoLastStepNum(self):
        test_input = ["-t"]
        # main(test_input)
        # if logger.isEnabledFor(logging.DEBUG):
        #     main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("expected one argument" in output)

    def testNonIntLastStepNum(self):
        test_input = ["-t", "ghost"]
        # main(test_input)
        # if logger.isEnabledFor(logging.DEBUG):
        #     main(test_input)
        with capture_stderr(main, test_input) as output:
            self.assertTrue("integer must be provided" in output)

    def testDirInsteadOfFile(self):
        test_input = ["-f", SUB_DATA_DIR, "-z"]
        with capture_stderr(main, test_input) as output:
            self.assertTrue("Problems reading file" in output)


class TestCheckGauss(unittest.TestCase):
    # These test/demonstrate different options
    def testBasicUse(self):
        test_input = ["-d", SUB_DATA_DIR]
        copyfile(NORM_TERM_LOG, TEMP_NORM_TERM_LOG)
        silent_remove(MOVED_FILE, disable=DISABLE_REMOVE)
        try:
            # main(test_input)
            # copyfile(NORM_TERM_LOG, TEMP_NORM_TERM_LOG)
            # silent_remove(MOVED_FILE, disable=DISABLE_REMOVE)
            with capture_stdout(main, test_input) as output:
                self.assertTrue(output == GOOD_OUT)
            self.assertFalse(diff_lines(MOVED_FILE, NORM_TERM_LOG))
            with capture_stderr(main, test_input) as output:
                self.assertTrue("not read" in output)
        finally:
            silent_remove(MOVED_FILE, disable=DISABLE_REMOVE)
            silent_remove(FOR_HARTREE_DIR, disable=DISABLE_REMOVE)
            pass

    def testSingleFinalConvergence(self):
        test_input = ["-f", SINGLE_FILE, "-z"]
        good_out = 'File                                 Convergence Convergence_Error\n'\
                   'me2propprpnt_7.log                      111.4981 True\n'
        with capture_stdout(main, test_input) as output:
            self.assertTrue(output == good_out)

    def testListFinalConvergence(self):
        test_input = ["-l", LIST_FILE, "-z"]
        # main(test_input)
        good_out = 'File                                 Convergence Convergence_Error\n' \
                   'hexyl_acrylate_419.log                    0.0706 False\n'\
                   'hexyl_acrylate_239.log                    1.1100 False\n'
        with capture_stdout(main, test_input) as output:
            self.assertTrue(output == good_out)

    def testListEachStepConvergence(self):
        test_input = ["-l", LIST_FILE, "-s"]
        try:
            main(test_input)
            self.assertFalse(diff_lines(CONV_239_OUT, GOOD_CONV_239_OUT))
            self.assertFalse(diff_lines(CONV_419_OUT, GOOD_CONV_419_OUT))
        finally:
            silent_remove(CONV_239_OUT, disable=DISABLE_REMOVE)
            silent_remove(CONV_419_OUT, disable=DISABLE_REMOVE)
            pass

    def testOneEachStepOut(self):
        # tests searching directory with checking convergence, plus using an alternate extension
        test_input = ["-s", "-d", SUB_DATA_DIR, "-e", ".out"]
        try:
            main(test_input)
            self.assertFalse(diff_lines(DIOXOLAN_OUT, GOOD_DIOXOLAN_OUT))
        finally:
            silent_remove(DIOXOLAN_OUT, disable=DISABLE_REMOVE)
            pass

    def testOneEachStopAtStep(self):
        # tests searching directory with checking convergence, plus using an alternate extension
        test_input = ["-t", "37", "-d", SUB_DATA_DIR, "-e", ".out"]
        good_output = "Steps sorted by convergence to step number 37 for file: dioxolan4ol_ts4_ts.out\n" \
                      "    StepNum  Convergence\n" \
                      "         35    161.099\n" \
                      "         37    211.219\n" \
                      "          1    342.935\n" \
                      "         36    392.523\n" \
                      "         34    456.271\n"
        # main(test_input)
        with capture_stdout(main, test_input) as output:
            self.assertTrue(output == good_output)

    def testBest10Steps(self):
        # tests searching directory with checking convergence, plus using an alternate extension
        test_input = ["-b", "-d", SUB_DATA_DIR, "-e", ".out"]
        good_output = "Best (up to 10) steps sorted by convergence for file: dioxolan4ol_ts4_ts.out\n" \
                      "    StepNum  Convergence\n" \
                      "         43      1.031\n" \
                      "         44      1.146\n" \
                      "         42     42.515\n" \
                      "         41     42.785\n" \
                      "         40     56.686\n" \
                      "         39    102.103\n" \
                      "         35    161.099\n" \
                      "         37    211.219\n" \
                      "         38    252.513\n" \
                      "          1    342.935\n"
        # main(test_input)
        with capture_stdout(main, test_input) as output:
            self.assertTrue(output == good_output)

    def testBest10StepsList(self):
        test_input = ["-b", "-l", LIST_FILE]
        good_output = "Best (up to 10) steps sorted by convergence for file: hexyl_acrylate_419.log\n" \
                      "    StepNum  Convergence\n" \
                      "          8      0.071\n" \
                      "          7      4.319\n" \
                      "          1    666.063\n" \
                      "Best (up to 10) steps sorted by convergence for file: hexyl_acrylate_239.log\n" \
                      "    StepNum  Convergence\n" \
                      "         17      1.110\n" \
                      "         16      1.138\n" \
                      "          1    749.248\n"
        # main(test_input)
        with capture_stdout(main, test_input) as output:
            self.assertTrue(output == good_output)
            pass

    def testAllStepsStdOutList(self):
        test_input = ["-a", "-l", LIST_FILE]
        good_output = "Convergence of all steps for file: hexyl_acrylate_419.log\n" \
                      "    StepNum  Convergence\n" \
                      "          1    666.063\n" \
                      "          7      4.319\n" \
                      "          8      0.071\n" \
                      "Convergence of all steps for file: hexyl_acrylate_239.log\n" \
                      "    StepNum  Convergence\n" \
                      "          1    749.248\n" \
                      "         16      1.138\n" \
                      "         17      1.110\n"
        # main(test_input)
        with capture_stdout(main, test_input) as output:
            print(output)
            self.assertTrue(output == good_output)
            pass
