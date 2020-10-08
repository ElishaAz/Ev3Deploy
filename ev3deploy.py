import sys
import threading
from pathlib import Path
import fnmatch
import os
import argparse

from paramiko import SSHClient
from scp import SCPClient
from typing import List, Optional, TextIO

PATH = './'
EXECUTABLE = ['*.py', '*.sh']
PASSWORD = "maker"
HOSTNAME = "ev3dev"
USERNAME = "robot"
IGNORE_PATH = "./.ignore"
EXECUTE_FILE = None


def read_exclude(ignore_path: str) -> List[str]:
    """
    Read the exclude file ('.ignore').
    :param ignore_path: Path to the exclude file.
    :return: A list of file patterns to ignore.
    """
    if not os.path.exists(Path(ignore_path)):
        ignore = open(Path(ignore_path), 'w+')
        ignore.writelines(['./.ignore\n', './ev3deploy.py\n', '*/.*'])
        ignore.close()

    ignore = open(ignore_path, 'r')
    lines = [line.strip() for line in ignore.readlines()]
    return lines


def match(filename: str, patterns: List[str]) -> bool:
    """
    Checks if filename matches ANY of 'patterns'.
    :param filename: A path of a file.
    :param patterns: A list of standard UNIX file patterns.
    :return: True if filename matches ANY of 'patterns', False otherwise.
    """
    for m in patterns:
        if fnmatch.fnmatch(filename, m):
            return True
    return False


def path_join(*paths) -> Optional[Path]:
    """
    Joins multiple strings to a single Path object.
    :param paths: paths to join.
    :return: A Path object corresponding to 'paths'. 'None' if 'paths' is empty.
    """
    if len(paths) < 1:
        return None
    res = Path(paths[0]).joinpath(*paths[1:])
    return res


def get_args() -> None:
    """
    Configures command line arguments.
    """
    global HOSTNAME, USERNAME, PASSWORD, PATH, IGNORE_PATH, EXECUTE_FILE
    parser = argparse.ArgumentParser(description='Send Project to Ev3.')
    parser.add_argument('--hostname', help="The ssh hostname (default is 'ev3dev')")
    parser.add_argument('--username', help="The ssh username (default is 'robot')")
    parser.add_argument('--password', help="The ssh password (default is 'maker')")
    parser.add_argument('--path', help="The Directory to send (default is current directory).")
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


def redirect_stdout_handler(st: TextIO):
    """
    Copies 'st' to system stdout.
    :param st: An output stream.
    """
    for l in iter(st.readline, ""):
        print(l, end="")


def redirect_stderr_handler(st: TextIO):
    """
    Copies 'st' to system stderr.
    :param st: An output stream.
    """
    for l in iter(st.readline, ""):
        print(l, end="", file=sys.stderr)


run_stdin = True


def redirect_stdin_handler(st: TextIO):
    """
    Copies system stdin to st.
    :param st: An input stream.
    """
    global run_stdin
    while run_stdin:
        # if sys.stdin.isatty():
        for line in sys.stdin:
            if st.closed or sys.stdin.closed or not run_stdin:
                break
            print(line, end="", file=st)


def deploy(path: str = './', hostname: str = "ev3dev", username: str = "robot", password: str = "maker",
           execute_file: Optional[str] = None, executable: List[str] = ('*.py',),
           exclude_path: str = "./.ignore", print_console: bool = True,
           redirect_stdout: bool = True, redirect_stderr: bool = True, redirect_stdin: bool = False) -> None:
    """
    Send code to Ev3
    :param path: The Directory to send (default is current directory).
    :param hostname: The ssh hostname (default is 'ev3dev')
    :param username: The ssh username (default is 'robot')
    :param password: The ssh password (default is 'maker')
    :param execute_file: A file to run on the ev3 when finished. 'None' to disable.
     Note: this file must be marked as executable.
    :param executable: A list of patterns of files that should be marked as executable (default is ['*.py']).
    :param exclude_path: The file containing the list of files to ignore (default is '.ignore').
    :param print_console: Should we print info to the console?
    :param redirect_stdout: Should we redirect stdout form ev3 to console?
    :param redirect_stderr: Should we redirect stderr form ev3 to console?
    :param redirect_stdin: Should we redirect console input to ev3 stdin?
     This is disabled by default as it cannot terminate without reading from stdin.
    """
    # Get / Set working directory
    if print_console:
        print("CD", path)
    os.chdir(path)
    working_dir = os.getcwd()
    dir_name = os.path.basename(working_dir)

    exclude = read_exclude(exclude_path)

    # Set up ssh
    if print_console:
        print("Starting ssh ...")
    ssh = SSHClient()
    ssh.load_system_host_keys()
    if print_console:
        print("Connecting to", F"{username}@{hostname} ...")
    ssh.connect(hostname=hostname, username=username, password=password)

    with SCPClient(ssh.get_transport()) as scp:
        for subdir, dirs, files in os.walk('.'):  # for every file in current working directory:
            for filename in files:
                filepath = subdir + '/' + filename  # get full file path (relative to working directory)
                if not match(filepath, exclude):  # if the file path does not match any of the excluded patterns:
                    if print_console:
                        print("Sending", Path(filepath), "...")
                    # create the directory if it does not exist
                    ssh.exec_command('mkdir -p ' + path_join('~', dir_name, subdir).as_posix())
                    # copy files using scp
                    scp.put(str(path_join(working_dir, filepath)), path_join('~', dir_name, filepath).as_posix())
                    if print_console:
                        print("Sent")
                    if match(filepath, executable):  # if file path matches any of the executable patterns:
                        # mark as executable
                        if print_console:
                            print(path_join('~', dir_name, filepath).as_posix(), "marked as executable.")
                        ssh.exec_command('chmod u+x ' + path_join('~', dir_name, filepath).as_posix())
                else:
                    if print_console:
                        print('Excluding', Path(filepath), '.')

        if execute_file:
            if print_console:
                print(F'\nExecuting {execute_file} ...\n')
            # execute the file.
            stdin, stdout, stderr = ssh.exec_command(path_join('~', dir_name, execute_file).as_posix(), get_pty=True)

            # create the rerouting threads
            if redirect_stdout:
                out = threading.Thread(target=redirect_stdout_handler, args=(stdout,))
            if redirect_stderr:
                err = threading.Thread(target=redirect_stderr_handler, args=(stderr,))
            if redirect_stdin:
                sin = threading.Thread(target=redirect_stdin_handler, args=(stdin,))

            # start them
            if redirect_stdout:
                out.start()
            if redirect_stderr:
                err.start()
            if redirect_stdin:
                sin.start()

            # wait for them to terminate
            if redirect_stdout:
                out.join()
            if redirect_stderr:
                err.join()
            if redirect_stdin:
                global run_stdin
                # tell reroute_stdin to exit without sending data to stdin
                run_stdin = False
                sys.stdin.close()
                sin.join()

            if print_console:
                print('\nFinished.')


if __name__ == '__main__':
    get_args()

    deploy(PATH, PASSWORD, HOSTNAME, USERNAME, EXECUTE_FILE, EXECUTABLE, IGNORE_PATH)
