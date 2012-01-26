"""
See:
www.surlyjake.com/2011/03/create-a-single-standalone-exe-from-a-python-program/


1.  grab pyinstaller 1.5rc (1.4 doesn't work with python 2.7).
    extract the zip file anywhere.

2. change directories to the pyinstaller folder you just created.

3. Before you create your first executable, you will have to run this once.

      python configure.py

4. Now, pyinstall needs to scan through your program and create what they
   call a spec file.

      python makespec.py --onefile path\to\program\program.py

5. Now, run this command to generate the executable.

      python build.py program\program.spec
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
