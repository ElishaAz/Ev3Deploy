import sys
import threading
from pathlib import Path
import fnmatch
import os
import argparse

from paramiko import SSHClient
from scp import SCPClient
from typing import List, Optional

PATH = './'
EXECUTABLE = ['*.py', '*.sh']
PASSWORD = "maker"
HOSTNAME = "ev3dev"
USERNAME = "robot"
IGNORE_PATH = "./.ignore"
EXECUTE_FILE = None


def read_exclude():
    if not os.path.exists(Path(IGNORE_PATH)):
        ignore = open(Path(IGNORE_PATH), 'w+')
        ignore.writelines(['./.ignore\n', './deploy.py\n', '*/.*'])
        ignore.close()

    ignore = open(IGNORE_PATH, 'r')
    lines = [line.strip() for line in ignore.readlines()]
    return lines


def find_dir(root: str = '.', exclude: List[str] = ('*/.*', './deploy.py')) -> List[str]:
    """
    :param root:
    :param exclude:
    :return:
    """
    res: List[str] = []

    for file in os.listdir(path=root):
        full_path = root + '/' + file
        if not match(full_path, exclude):
            # res.append(full_path)
            if os.path.isdir(Path(full_path)):
                # print("DIR", file)
                res += find_dir(full_path)
            else:
                # print("DOC", file)
                res.append(full_path)
        else:
            print("Excluded", file)
    return res


def match(filename: str, matches: List[str]):
    """

    :param filename:
    :param matches:
    :return:
    """
    for m in matches:
        if fnmatch.fnmatch(filename, m):
            return True
    return False


def path_join(*path) -> Optional[Path]:
    if len(path) < 1:
        return None
    res = None
    res = Path(path[0]).joinpath(*path[1:])
    # for p in path:
    #     if res is None:
    #         res = Path(p)
    #     else:
    #         res.joinpath(p)
    # print(res)
    return res


def get_args():
    global HOSTNAME, USERNAME, PASSWORD, PATH, IGNORE_PATH, EXECUTE_FILE
    parser = argparse.ArgumentParser(description='Send Project to Ev3.')
    parser.add_argument('--hostname', help="The ssh hostname (default is 'ev3dev')")
    parser.add_argument('--username', help="The ssh username (default is 'robot')")
    parser.add_argument('--password', help="The ssh password (default is 'maker')")
    parser.add_argument('--path', help="The Directory to send (default is working directory).")
    parser.add_argument('--exclude_file',
                        help="The file containing the list of files to ignore (default is '.ignore').")
    parser.add_argument('--execute_file', help="A file to execute after transferring (local path relative to 'PATH').")

    args = parser.parse_args()

    if args.hostname:
        HOSTNAME = args.hostname
    if args.username:
        USERNAME = args.username
    if args.password:
        PASSWORD = args.password

    if args.path:
        PATH = args.path

    if args.exclude_file:
        IGNORE_PATH = args.exclude_file

    if args.execute_file:
        EXECUTE_FILE = args.execute_file


def reroute_stdout(stdout):
    for l in iter(stdout.readline, ""):
        print(l, end="")


def reroute_stderr(stderr):
    for l in iter(stderr.readline, ""):
        print(l, end="", file=sys.stderr)


run_stdin = True


def reroute_stdin(stdin):
    while run_stdin:
        print(input(), end="", file=stdin)


if __name__ == '__main__':
    get_args()

    os.chdir(PATH)

    DIR = os.getcwd()
    DIR_NAME = os.path.basename(DIR)

    # files = find_dir('.', read_exclude())
    print(read_exclude())

    exclude = read_exclude()

    ssh = SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(hostname=HOSTNAME, username=USERNAME, password=PASSWORD)

    with SCPClient(ssh.get_transport()) as scp:
        for subdir, dirs, files in os.walk('.'):
            for filename in files:
                filepath = subdir + '/' + filename
                if match(filepath, exclude):
                    print('Excluding', Path(filepath))
                else:
                    print("Sending", Path(filepath))
                    ssh.exec_command('mkdir -p ' + path_join('~', DIR_NAME, subdir).as_posix())
                    scp.put(str(path_join('.', filepath)), path_join('~', DIR_NAME, filepath).as_posix())
                    if match(filepath, EXECUTABLE):
                        ssh.exec_command('chmod u+x ' + path_join('~', DIR_NAME, filepath).as_posix())

        if EXECUTE_FILE:
            print(F'\nExecuting {EXECUTE_FILE} ...\n')
            stdin, stdout, stderr = ssh.exec_command(path_join('~', DIR_NAME, EXECUTE_FILE).as_posix(), get_pty=True)

            out = threading.Thread(target=reroute_stdout, args=(stdout,))
            err = threading.Thread(target=reroute_stderr, args=(stderr,))
            sin = threading.Thread(target=reroute_stdin, args=(stdin,))

            out.start()
            err.start()
            sin.start()

            out.join()
            err.join()

            run_stdin = False

            sin.join()

            print('\nFinished.')
