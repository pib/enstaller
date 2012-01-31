#!/bin/bash
# Script to build the self-bootstraping, indexable enstaller egg.
# The resulting egg is executable, but only on systems which have
# bash installed.

# Build notes:
#   * setuptools needs to be installed to run this script

VER=4.5.0

SPEC=enstaller.egg-info/spec
mkdir -p $SPEC
sed -e "s/_VER_/$VER/" <<EOF >$SPEC/depend
metadata_version = '1.1'
name = 'enstaller'
version = '_VER_'
build = 1

arch = None
platform = None
osdist = None
python = None
packages = []
EOF

sed -e "s/_VER_/$VER/" <<EOF >enstaller.egg-info/info.json
{
  "build": 1,
  "name": "enstaller",
  "version": "_VER_"
}
EOF

EGG=dist/enstaller-$VER-1.egg
rm -rf build dist
python setup.py bdist_egg
cat <<EOF >tmp.sh
#!/bin/bash
python -c "import sys, os; sys.path.insert(0, os.path.abspath('\$0')); from egginst.bootstrap import cli; cli()" "\$@"
exit 0
EOF
cat tmp.sh dist/enstaller-*-py*.egg >$EGG
rm -f tmp.sh dist/enstaller-*-py*.egg
chmod +x $EGG

egginfo --sd $EGG
#repo-upload --force --no-confirm $EGG
