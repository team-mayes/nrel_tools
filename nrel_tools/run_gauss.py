#!/usr/bin/env python
"""
makes and runs gaussian input
"""

from __future__ import print_function
import sys
import argparse
import subprocess
import re
import os
from nrel_tools.common import (InvalidDataError, warning, process_cfg, create_out_fname,
                               GOOD_RET, INPUT_ERROR, IO_ERROR, INVALID_DATA, GAU_HEADER_PAT,
                               read_tpl, InvalidInputError, str_to_file)
from nrel_tools.fill_tpl import (OUT_DIR, MAIN_SEC, fill_save_tpl)

try:
    # noinspection PyCompatibility
    from ConfigParser import ConfigParser, MissingSectionHeaderError
except ImportError:
    # noinspection PyCompatibility
    from configparser import ConfigParser, MissingSectionHeaderError

__author__ = 'hmayes'


# Constants #

# Config keys
CONFIG_FILE = 'config_file_name'
JOB_LIST = 'job_list'
FOLLOW_JOBS_LIST = 'follow_job_list'
GAUSS_IN_EXT = 'gaussian_input_ext'
TPL_DICT = 'dictionary of tpls for jobs'
JOB_RUN_TPL = "job_run_tpl"
FIRST_JOB_CHK = 'chk_for_first_job'
OLD_CHECK_ECHO = 'old_check_echo'
# config keys for spawning additional jobs
SBATCH_TPL = 'sbatch_tpl'
PARTITION = 'partition'
RUN_TIME = 'run_time'
ACCOUNT = 'account'
EMAIL = 'email'
ALL_NEW = 'all_new'
OPT_OLD_JOB_NAME = 'opt_old_name'
RUN_GAUSS_INI = 'run_gauss_ini'
QOS = 'qos'
LIST_OF_JOBS = 'list_of_jobs'
SETUP_SUBMIT = 'setup_submit'
START_FROM_SAME_CHK = 'start_from_job_name_chk'
NO_SUBMIT = 'no_submit'
CHECK_FOR_CHK = "check_for_chk"
STR_KEYS_FOR_SPAWNING_INIS = [JOB_RUN_TPL, PARTITION, QOS, RUN_TIME, ACCOUNT, SBATCH_TPL, EMAIL,
                              OLD_CHECK_ECHO]
NON_STR_KEYS_FOR_SPAWNING_INIS = [ALL_NEW, OUT_DIR, FIRST_JOB_CHK]

DEF_CFG_FILE = 'run_gauss.ini'
DEF_JOB_RUN_TPL = 'run_gauss_job.tpl'
DEF_GAUSS_IN_EXT = '.com'
DEF_JOB_LIST = None
DEF_PARTITION = 'short'
DEF_RUN_TIME = '4:00:00'
DEF_ACCOUNT = 'bpms'
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DEF_SBATCH_TPL = os.path.join(DATA_DIR, 'sbatch.tpl')
DEF_FOLLOW_JOBS_LIST = None
DEF_OLD_CHK_STR = 'echo "%OldChk={}.chk" >> $INFILE'

# Set notation
DEF_CFG_VALS = {OUT_DIR: None,
                GAUSS_IN_EXT: DEF_GAUSS_IN_EXT,
                JOB_RUN_TPL: DEF_JOB_RUN_TPL,
                JOB_LIST: None,
                FOLLOW_JOBS_LIST: DEF_FOLLOW_JOBS_LIST,
                FIRST_JOB_CHK: None,
                PARTITION: DEF_PARTITION,
                RUN_TIME: DEF_RUN_TIME,
                ACCOUNT: DEF_ACCOUNT,
                EMAIL: None,
                ALL_NEW: False,
                SBATCH_TPL: DEF_SBATCH_TPL,
                QOS: 'normal',
                START_FROM_SAME_CHK: False,
                OLD_CHECK_ECHO: DEF_OLD_CHK_STR,
                CHECK_FOR_CHK: True,
                }
REQ_KEYS = {
            }

JOB_NAME = 'job_name'
OLD_JOB_NAME = 'old_job_name'
INPUT_FILE = 'input_file'
GAU_GOOD_PAT = re.compile(r"Normal termination of Gaussian.*")
GUESS_READ_OR_GEOM_CHK_PAT = re.compile(r"^.*\b(guess.*read|geom.*check)\b.*$", re.I)


def read_cfg(f_loc, cfg_proc=process_cfg):
    """
    Reads the given configuration file, returning a dict with the converted values supplemented by default values.

    :param f_loc: The location of the file to read.
    :param cfg_proc: The processor to use for the raw configuration values.  Uses default values when the raw
        value is missing.
    :return: A dict of the processed configuration file's data.
    """
    config = ConfigParser()
    good_files = config.read(f_loc)

    if not good_files:
        raise IOError('Could not read file {}'.format(f_loc))
    main_proc = cfg_proc(dict(config.items(MAIN_SEC)), DEF_CFG_VALS, REQ_KEYS, int_list=False, store_extra_keys=True)

    main_proc[CONFIG_FILE] = f_loc
    main_proc[TPL_DICT] = {}

    all_job_types = []
    for job_list_key in [JOB_LIST, FOLLOW_JOBS_LIST]:
        job_list = main_proc[job_list_key]
        jobs_list = []
        # need to distinguish between NoneType and ''
        if job_list is not None:
            threads = [thread.split(',') for thread in job_list.split(';')]
            for thread in threads:
                thread = [job.strip() for job in thread]
                jobs_list.append(thread)
                all_job_types += thread
            main_proc[job_list_key] = jobs_list
        else:
            main_proc[job_list_key] = []

    for job in all_job_types:
        if job == '':
            continue
        if job in main_proc:
            tpl_name = main_proc[job]
        else:
            tpl_name = job + '.tpl'
        if os.path.isfile(tpl_name):
            main_proc[TPL_DICT][job] = tpl_name
        else:
            raise InvalidDataError("For job '{}', could not find a template file '{}'\n"
                                   "You may specify the template to use (including path) using {} as a key in the "
                                   "config file.".format(job, tpl_name, job))

    if not os.path.isfile(main_proc[JOB_RUN_TPL]):
        raise InvalidDataError("Could not find the submit template '{}'".format(main_proc[JOB_RUN_TPL]))

    return main_proc


def parse_cmdline(argv):
    """
    Returns the parsed argument list and return code.
    `argv` is a list of arguments, or `None` for ``sys.argv[1:]``.
    """
    if argv is None:
        argv = sys.argv[1:]

    # initialize the parser object:
    parser = argparse.ArgumentParser(description='Sets up and runs series of Gaussian jobs, checking between jobs '
                                                 'for normal termination.')
    parser.add_argument("job_name", help="The job name to run. If the first job to run is '', a Gaussian input file "
                                         "(with extension '{}' or specified with '{}' argument in the config file) is "
                                         "needed. Otherwise, a checkpoint file (with extension '.chk') is "
                                         "needed.".format(DEF_GAUSS_IN_EXT, GAUSS_IN_EXT))
    parser.add_argument("-c", "--config", help="The location of the configuration file in ini format. "
                                               "The default file name is {}, located in the base directory "
                                               "where the program as run.".format(DEF_CFG_FILE),
                        default=DEF_CFG_FILE, type=read_cfg)
    parser.add_argument("-n", "--no_submit", help="Set up jobs without submitting them. This flag only effects the "
                                                  "'-s' and '-l' options.", action="store_true", default=False)
    parser.add_argument("-o", "--old_chk_file", help="The base name of the checkpoint file (do not include '.chk')"
                                                     "to be used for the first job (optional).", default=None)
    parser.add_argument("-s", "--setup_submit", help="The script will setup and submit, rather than run, the provided "
                                                     "'job_name'. Any extension, or none, can be included in the job "
                                                     "name. If a 'single_job' or 'list_of_jobs' are not specified, "
                                                     "the script will instead attempt to run the 'job_name'. The "
                                                     "default is False.", action="store_true", default=False)
    parser.add_argument("-l", "--list_of_jobs", help="The input in the position of 'job_name' will be read as a file "
                                                     "name with a list of jobs to set up and submit. Each job name "
                                                     "should be on a separate line. Any extension, or none, can follow "
                                                     "the job name. If a 'setup_submit' or 'list_of_jobs' are not "
                                                     "specified, the script will instead attempt to run the 'job_name'."
                                                     " The default is False.", action="store_true", default=False)
    parser.add_argument("-t", "--testing", help="Run in testing mode, which will not check for normal Gaussian "
                                                "termination before continuing. Default is False.",
                        action="store_true", default=False)

    args = None
    try:
        args = parser.parse_args(argv)
        if args.setup_submit and args.list_of_jobs:
            raise InvalidDataError("Cannot choose both 'setup_submit' and 'list_of_jobs' options")
        if args.list_of_jobs:
            if not os.path.isfile(args.job_name):
                raise IOError("When using the 'list_of_jobs' option, the first positional argument ('job_name') must "
                              "be the name of the file with the list of jobs. Could not read: {}".format(args.job_name))
        if args.old_chk_file:
            args.config[FIRST_JOB_CHK] = os.path.splitext(args.old_chk_file)[0]

        if not (args.list_of_jobs or args.setup_submit):
            if len(args.config[JOB_LIST]) > 1:
                raise InvalidDataError("Found ';' in the '{}'. This option (setting up multiple job threads) is "
                                       "currently only supported for setting up (and optionally submitting) jobs "
                                       "(using the '-s' or '-l' options).".format(JOB_LIST))
            elif len(args.config[JOB_LIST]) == 1:
                args.config[JOB_LIST] = args.config[JOB_LIST][0]

        # commenting below made the current directory the default
        # if not args.config[OUT_DIR]:
        #     args.config[OUT_DIR] = os.path.dirname(args.config[CONFIG_FILE])
    except IOError as e:
        warning("Problems reading file:", e)
        parser.print_help()
        return args, IO_ERROR
    except (KeyError, InvalidDataError, MissingSectionHeaderError, SystemExit) as e:
        if hasattr(e, 'code') and e.code == 0:
            return args, GOOD_RET
        warning(e)
        parser.print_help()
        return args, INPUT_ERROR

    return args, GOOD_RET


def run_job(job, job_name_perhaps_with_dir, tpl_dict, cfg, testing_flag):
    # Determine if it will run fresh or from an old checkpoint
    if job == '':
        new_job_name = tpl_dict[JOB_NAME]
        tpl_dict[INPUT_FILE] = job_name_perhaps_with_dir + cfg[GAUSS_IN_EXT]
        if cfg[FIRST_JOB_CHK]:
            tpl_dict[OLD_CHECK_ECHO] = cfg[OLD_CHECK_ECHO].format(cfg[FIRST_JOB_CHK])
        else:
            tpl_dict[OLD_CHECK_ECHO] = ''
    else:
        new_job_name = tpl_dict[JOB_NAME] + '_' + job
        tpl_dict[OLD_JOB_NAME] = tpl_dict[JOB_NAME]
        tpl_dict[OLD_CHECK_ECHO] = cfg[OLD_CHECK_ECHO].format(tpl_dict[OLD_JOB_NAME])
        tpl_dict[INPUT_FILE] = cfg[TPL_DICT][job]
    if not os.path.isfile(tpl_dict[INPUT_FILE]):
        raise IOError(tpl_dict[INPUT_FILE])

    tpl_file = cfg[JOB_RUN_TPL]
    job_runner_fname = create_out_fname(new_job_name, ext=".sh", base_dir=cfg[OUT_DIR])
    print("Running {}".format(new_job_name))

    tpl_dict[JOB_NAME] = new_job_name
    tpl_str = read_tpl(tpl_file)
    fill_save_tpl(cfg, tpl_str, tpl_dict, tpl_file, job_runner_fname)
    subprocess.call(["chmod", "+x", job_runner_fname])
    p1 = subprocess.Popen(job_runner_fname)
    p1.wait()
    if testing_flag:
        print("Testing mode; did not check for normal Gaussian termination.")
    else:
        out_file = tpl_dict[JOB_NAME] + ".log"
        last_line = subprocess.check_output(["tail", "-1",  out_file]).strip().decode("utf-8")
        if GAU_GOOD_PAT.match(last_line):
            print("Successfully completed {}".format(out_file))
            os.remove(job_runner_fname)
        else:
            raise InvalidDataError('Job failed: {}'.format(out_file))


def create_sbatch_dict(cfg, tpl_dict, new_ini_fname, current_job_list, start_from_job_name_chk=True):
    sbatch_dict = {PARTITION: cfg[PARTITION], RUN_TIME: cfg[RUN_TIME], ACCOUNT: cfg[ACCOUNT],
                   JOB_NAME: tpl_dict[JOB_NAME], RUN_GAUSS_INI: new_ini_fname, QOS: cfg[QOS]
                   }

    if cfg[FIRST_JOB_CHK]:
        sbatch_dict[OPT_OLD_JOB_NAME] = '-o ' + cfg[FIRST_JOB_CHK]
    elif start_from_job_name_chk:
        sbatch_dict[OPT_OLD_JOB_NAME] = '-o ' + tpl_dict[JOB_NAME]
    else:
        sbatch_dict[OPT_OLD_JOB_NAME] = ''
        if current_job_list[0] == '' and cfg[CHECK_FOR_CHK]:
            # in the case when there is no old_check_file, make sure the first input file does not try to read from chk
            # IOError is already caught; no don't need to add a try loop
            with open(tpl_dict[INPUT_FILE], "r") as f:
                for line in f:
                    line = line.strip()
                    # route can be multiple lines, so first fine the line, then continue until a blank is reached
                    if GAU_HEADER_PAT.match(line):
                        while line != '':
                            if GUESS_READ_OR_GEOM_CHK_PAT.match(line):
                                raise InvalidDataError("Did not find an old checkpoint file to read, but the "
                                                       "Gaussian input header indicates that Gaussian will attempt "
                                                       "and fail to read from a checkpoint:\n   file:  {}\n"
                                                       "  route:  {} ".format(tpl_dict[INPUT_FILE], line))
                            line = next(f).strip()

    if cfg[EMAIL]:
        sbatch_dict[EMAIL] = '#SBATCH --mail-type=FAIL\n#SBATCH --mail-type=END\n' \
                             '#SBATCH --mail-user={}'.format(cfg[EMAIL])
    else:
        sbatch_dict[EMAIL] = ''

    return sbatch_dict


def add_to_ini(filled_tpl_name, thread, tpl_dict):
    with open(filled_tpl_name, 'a') as f:
        f.write('\n')
        for job in thread:
            if job == '':
                continue
            f.write('{} = {}\n'.format(job, tpl_dict[job]))


def create_ini_dict(cfg, thread):
    ini_dict = {JOB_LIST: ','.join(thread)}
    # most of the next are for setting up submits with spawning; doesn't hurt if not needed
    for key_word in STR_KEYS_FOR_SPAWNING_INIS:
        # if the cfg values are not strings, they have to be treated differently
        ini_dict[key_word] = cfg[key_word]
    jobs_string = None
    if len(cfg[FOLLOW_JOBS_LIST]) > 0 and (cfg[SETUP_SUBMIT] or cfg[LIST_OF_JOBS]):
        thread_list = []
        for thread in cfg[FOLLOW_JOBS_LIST]:
            thread_list.append(','.join(thread))
        jobs_string = ';'.join(thread_list)
    ini_dict[FOLLOW_JOBS_LIST] = jobs_string

    return ini_dict


def create_ini_tpl_with_req_keys(ini_dict, thread, tpl_dict, cfg, new_ini_fname):
    """
    Adds to the ini_tpl if a non-default parameter needs to be specified, and is not already included
    :param thread: the jobs to be run, to check that if a location of the tpl is specified, it gets included
                   in the new ini file
    :param tpl_dict: dictionary of locations of job tpl files
    :param new_ini_fname: name and location of the ini_tpl created
    :param ini_dict: values for filling
    :param cfg: configuration dict
    :return: tpl_str: str with values to be filled
    """
    # we always need the header, job_list, and job_run_tpl
    tpl_str = '[main]\njob_run_tpl = {}\njob_list = {}'.format(ini_dict[JOB_RUN_TPL], ini_dict[JOB_LIST])

    # check for not None, because want this check to catch if it is ''
    # if not none, make sure it has the keys needed to make a new ini with sbatch options
    if ini_dict[FOLLOW_JOBS_LIST] is not None:
        tpl_str += '\n{} = {}'.format(FOLLOW_JOBS_LIST, ini_dict[FOLLOW_JOBS_LIST])
        # I've checked that this list all has default vals and is added to ini_dict, so no catch added
        # opt = tests/test_data/run_gauss/opt.tpl
        # stable = tests/test_data/run_gauss/stable.tpl
        # freq = tests/test_data/run_gauss/freq.tpl
        for key_word in STR_KEYS_FOR_SPAWNING_INIS:
            # if the value is not what is default, check if it will be printed in the created ini
            # (by checking the tpl_str). If not, add to the tpl_str.
            if ini_dict[key_word] != DEF_CFG_VALS[key_word]:
                if not (key_word in tpl_str):
                    # might as well just fill in the value here; easier than setting it up to be filled later
                    tpl_str += '\n{} = {}'.format(key_word, ini_dict[key_word])
        # the keys below were not already added to the ini_dict, which skipped any keys with non-string values
        # add to tpl_str now
        for key_word in NON_STR_KEYS_FOR_SPAWNING_INIS:
            if key_word not in tpl_str:
                if cfg[key_word] != DEF_CFG_VALS[key_word]:
                    tpl_str += '\n{} = {}'.format(key_word, cfg[key_word])
    # whether or not sbatch options are needed, job locations will be needed
    for job in thread:
        if job != '':
            tpl_str += '\n{} = {}'.format(job, tpl_dict[job])

    str_to_file(tpl_str, new_ini_fname, print_info=True)


def setup_and_submit(cfg, suffix, thread, tpl_dict, current_job_list):
    ini_dict = create_ini_dict(cfg, thread)

    if cfg[SETUP_SUBMIT] or cfg[LIST_OF_JOBS]:
        base_name = tpl_dict[JOB_NAME]
    else:
        base_name = cfg[CONFIG_FILE]

    new_ini_fname = create_out_fname(base_name, suffix=str(suffix), ext='.ini', base_dir=cfg[OUT_DIR])
    new_sbatch_fname = create_out_fname(base_name, suffix=str(suffix), ext='.slurm', base_dir=cfg[OUT_DIR])

    sbatch_dict = create_sbatch_dict(cfg, tpl_dict, os.path.relpath(new_ini_fname), current_job_list,
                                     start_from_job_name_chk=cfg[START_FROM_SAME_CHK])
    tpl_str = read_tpl(cfg[SBATCH_TPL])
    fill_save_tpl(cfg, tpl_str, sbatch_dict, cfg[SBATCH_TPL], new_sbatch_fname)

    # read ini_tpl and check if it has fields for submitting spawned jobs, if needed
    create_ini_tpl_with_req_keys(ini_dict, thread, cfg[TPL_DICT], cfg, new_ini_fname)

    if not cfg[NO_SUBMIT]:
        try:
            sbatch_result = subprocess.check_output(["sbatch", new_sbatch_fname]).strip().decode("utf-8")
            print(sbatch_result)
        except IOError as e:
            print(e)


def main(argv=None):
    # Read input
    args, ret = parse_cmdline(argv)
    if ret != GOOD_RET or args is None:
        return ret

    cfg = args.config
    # to keep these values handy
    cfg[LIST_OF_JOBS] = args.list_of_jobs
    cfg[SETUP_SUBMIT] = args.setup_submit
    cfg[NO_SUBMIT] = args.no_submit

    # Read template and data files
    try:
        # for the "list_of_jobs" option, "job_name" is actually the name of the name of file with the list of jobs
        if args.list_of_jobs:
            with open(args.job_name) as f:
                for line in f:
                    input_job_file = os.path.splitext(line.strip())[0] + cfg[GAUSS_IN_EXT]
                    base_name = os.path.splitext(os.path.basename(line.strip()))[0]
                    tpl_dict = {JOB_NAME: base_name, INPUT_FILE: input_job_file}
                    for index, thread in enumerate(cfg[JOB_LIST]):
                        if len(cfg[JOB_LIST]) == 1:
                            suffix = ''
                        else:
                            suffix = index
                        setup_and_submit(cfg, suffix, thread, tpl_dict, thread)
            return GOOD_RET

        # otherwise, job_name is actually the job name. We can to ignore any extension on it
        job_name_perhaps_with_dir = os.path.splitext(args.job_name)[0]
        job_name = os.path.basename(job_name_perhaps_with_dir)
        tpl_dict = {JOB_NAME: job_name, INPUT_FILE: job_name_perhaps_with_dir + cfg[GAUSS_IN_EXT]}

        if args.setup_submit:
            for index, thread in enumerate(cfg[JOB_LIST]):
                if len(cfg[JOB_LIST]) == 1:
                    suffix = ''
                else:
                    suffix = index
                setup_and_submit(cfg, suffix, thread, tpl_dict, thread)
            return GOOD_RET

        for job in cfg[JOB_LIST]:
            run_job(job, job_name_perhaps_with_dir, tpl_dict, cfg, args.testing)

        if len(cfg[FOLLOW_JOBS_LIST]) > 1:
            for index, thread in enumerate(cfg[FOLLOW_JOBS_LIST]):
                if index == 0 and not cfg[ALL_NEW]:
                    continue
                setup_and_submit(cfg, index, thread, tpl_dict, thread)

        if len(cfg[FOLLOW_JOBS_LIST]) > 0 and not cfg[ALL_NEW]:
            for job in cfg[FOLLOW_JOBS_LIST][0]:
                run_job(job, job_name_perhaps_with_dir, tpl_dict, cfg, args.testing)

    except IOError as e:
        warning("Problems reading file:", e)
        return IO_ERROR
    except subprocess.CalledProcessError as e:
        warning("", e)
    except InvalidInputError as e:
        warning("Check input:", e)
        return INVALID_DATA
    except InvalidDataError as e:
        warning("Problems reading data:", e)
        return INVALID_DATA

    return GOOD_RET  # success


if __name__ == '__main__':
    status = main()
    sys.exit(status)
