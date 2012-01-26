"""
See:

"""
import os
import sys
import shutil
from subprocess import check_call
from os.path import abspath, isdir, join


pyinst_dir = r"C:\tmp\pyinstaller-1.5.1"


def main():
    subdir = join(pyinst_dir, "launch")
    if isdir(subdir):
        shutil.rmtree(subdir)

    check_call([sys.executable, "Makespec.py", "--onefile",
                abspath("launch.py")],
                cwd=pyinst_dir)

    check_call([sys.executable, "Build.py",
                join(subdir, "launch.spec")],
                cwd=pyinst_dir)

    shutil.copy(join(subdir, "dist", "launch.exe"), os.getcwd())


if __name__ == '__main__':
    main()
