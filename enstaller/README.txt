The index.json file maps keys (which are the egg filenames) to
info dictionaries.  These dictionaries have the following keys:

Required:
---------
name       the name of the package (lowercase) (string)
version    the version (string)
build      build number (integer)
size       the file size in bytes (integer)
md5        the MD5 hashsum of the file
mtime      the file modification time (seconds since Unix epoch) (float)


Optional:
---------
packages   list of dependency packages, e.g. ['numpy 1.6.1', 'scipy'],
           defaults to [], i.e. no dependencies
python     the Python version the package is build for, defaults to '2.7'
type       defaults to 'egg'
available  boolean which indicated whether the file (egg) is available,
           defaults to True
