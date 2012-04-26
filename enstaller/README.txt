The index.json file maps keys (which are the egg filenames) to
info dictionaries.  These dictionaries have the following keys:

Required:
---------
name       name of the package (lowercase) (string)
version    version (string)
build      build number (integer)
size       file size in bytes (integer)
md5        MD5 hashsum of the file
mtime      file modification time (seconds since Unix epoch) (float)


Optional:
---------
packages   list of dependency packages, e.g. ['numpy 1.6.1', 'scipy'],
           defaults to [], i.e. no dependencies
python     Python version the package is build for, defaults to '2.7'
type       defaults to 'egg'
available  boolean which indicated whether the file (egg) is available,
           i.e. whether one is privileged to download the file,
           defaults to True


Note that these are the only keys which enstaller cares about.
One might add other ones, which the Enpkg query methods will respect
and pass along, but the behaviour of enstaller itself is not
affected by their values.
