"""
Repository API
==============

This module specifies the repository API for the various package management
and installation systems that are in use at Enthought and our clients.
The Repository API exposes a key-value store interface on top of whatever
backend implementation is used by subclasses. This permits code which requires
access to a repository to use it in a uniform way without having to care about
where and how the data is stored.

Keys
----
The keys of the key value store are strings, and the repository API makes no
assumptions about what the strings represent or any structure they might have.
In particular keys are assumed to be case sensitive and may include arbitrary
characters, so repository implementations should be careful to handle any
issues which may arise if the underlying data store is case insensitive and
has special characters which need to be escaped.
Each key has associated with it a collection of metadata and some binary data.
The repository API makes no assumptions about how the metadata and data is
serialized.

Metadata
--------

Metadata should be representable as a dictionary whose keys are valid Python
identifiers, and whose values can be serialized into reasonable human-readable
form (basically, you should be able to represent the dictionary as JSON, XML,
YAML, or similar in a clear and sane way, because some underlying datastore
will).
Metadata can be retrieved via the get_metadata() method, or from the .meta
attribute on the file-like object returned by the get() method.  Metadata can
be attached to the file-like object that is given to the set() method or
updated for an existing object using update_metadata().  The repository
implementation may supply additional metadata items, or override
supplied ones, based upon the requirements of the repository, or the binary
object being stored. For example, a repository may provide a 'size' metadata
item for every key, and will not permit this value to be anything other than
the size of the binary data that is stored in the value.
We currently make no assumptions about the metadata keys, but we expect
conventions to evolve for the meanings and format of particular keys.  Given
that this is generally thought of as a repository for storing eggs, the
following metadata keys are likely to be available:

type:
The type of object being stored (package, app, patch, video, etc.).

name:
The name of the object being stored.

version:
The version of the object being stored.

arch:
The architecture that the object being stored is for.

python:
The version of Python that the object being stored is for.

ctime:
The creation time of the object in the repository in seconds since
the Unix Epoch.

mtime:
The last modification time of the object in the repository in seconds
since the Unix Epoch.

size:
The size of the binary data in bytes.

Data
----

The binary data stored in the values is presented through the repository API
as file-like objects which implement read(), close(), the standard file-like
context manager.  Frequently this will be a standard file, socket or StringIO
object. The read() method should accept an optional number of bytes to read,
so that buffered reads can be performed. In other words, a user of the
repository

API should be able to write::

with repo.get(key) as data_source:

data = data_source.read()

and have the context manager automatically dispose of any underlying system
resources which the file-like object needs via its close() method.
Similarly, for writable repositories, data should be supplied to keys via the
same sort of file-like object. This allows copying between repositories using

code like::

repo1.set(key, repo1.get(key))

Since files are likely to be common targets for extracting data from values, or
sources for data being stored, the repository API provides utility methods
to_file() and from_file(). Simple default implementations of these methods are
provided, but implementations of the repository API may be able to override
these to be more efficient, depending on the nature of the back-end data store.

Querying

--------

A very simple querying API is provided by default

"""

from abc import ABCMeta, abstractmethod

class AbstractRepo:

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, location):
        raise NotImplementedError

    @abstractmethod
    def connect(self, auth=None):
        """ Connect to the repository, optionally with authentication
        """
        raise NotImplementedError

    @abstractmethod
    def info(self):
        """ Get information about the repository

        Returns
        -------
        metadata : dict
            A dictionary of metadata giving information about the repository.
        """
        raise NotImplementedError

    ######################################################################
    # Create/Read/Update/Delete Methods
    ######################################################################

    @abstractmethod
    def get(self, key, default=None):
        """ Retrieve a stream from a given key in the repository.

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.
        default : None or file-like
            A default value to return if the key is not found in the repository.

        Returns
        -------
        data : file-like
            An object that provides stream of data from the repository. The
            object must implement at least read() and close() methods.
        """
        raise NotImplementedError

    def set(self, key, value, buffer_size=1048576):
        """ Store a stream of data into a given key in the repository.
        This may be left unimplemented by subclasses that represent a
        read-only repository.

        Parameters
        ----------

        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.
        value : file-like
            An object providing a stream of data to store into the repository.
            The object must implement at least read() and close() methdos.
        buffer_size : int
            An optional indicator of the number of bytes to read at a time.
            Implementations are free to ignore this hint or use a different
            default if they need to. The default is 1048576 bytes (1 MiB).
        """
        raise NotImplementedError

    def delete(self, key):
        """ Delete a key from the repsository.

        This may be left unimplemented by subclasses that represent a
        read-only repository.

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.
        """
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, key, default=None):
        """Retrieve the metadata for a given key in the repository.

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.

        default : None or dict
            A default value to return if the key is not found in the repository.

        Returns
        -------
        metadata : dict
            A dictionary of metadata associated with the key. The dictionary
            keys should be strings which are valid Python identifiers.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key):
        """ Test whether or not a key exists in the repository

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.

        Returns
        -------
        exists : bool
            Whether or not the key exists in the repository.
        """
        raise NotImplementedError

    ######################################################################
    # Querying Methods
    ######################################################################

    @abstractmethod
    def query(self, **kwargs):
        """ Query for keys and metadata matching metadata provided as keyword
        arguments
        This provides a very simple querying interface that returns precise
        matches with the metadata. If no arguments are supplied, the query
        will return the complete set of metadata for the repository.

        Parameters
        ----------
        **kwargs :
            Arguments where the keywords are metadata keys, and values are
            possible values for that metadata item.

        Returns
        -------
        result : dictionary
            A dictionary whose keys are repository keys whose metadata matches
            all the specified values for the specified metadata keywords. The
            values of the returned dictionary are the metadata.
        """
        raise NotImplementedError

    def query_keys(self, **kwargs):
        """ Query for keys matching metadata provided as keyword arguments

        This provides a very simple querying interface that returns precise
        matches with the metadata. If no arguments are supplied, the query
        will return the complete set of keys for the repository.
        This is equivalent to self.query(**kwargs).keys(), but potentially
        more efficiently implemented.

        Parameters
        ----------
        **kwargs :
            Arguments where the keywords are metadata keys, and values are
            possible values for that metadata item.

        Returns
        -------
        result : list
            A list of repository keys whose metadata matches all the specified
            values for the specified metadata keywords.
        """
        for key, dummy in self.query(**kwargs):
            yield key

    def glob(self, pattern, metadata=False):
        """ Return keys which match glob-style patterns

        Parameters
        ----------
        pattern : string
            Arguments where the keywords are metadata keys, and values are
            possible values for that metadata item.

        Returns
        -------
        result : list
            A list of repository keys whose metadata matches all the specified
            values for the specified metadata keywords.
        """
        raise NotImplementedError

    ######################################################################
    # Utility Methods
    ######################################################################

    def to_file(self, key, path, buffer_size=1048576):
        """ Efficiently store the data associated with a key into a file

        This method can be optionally overriden by subclasses to proved a more
        efficient way of copy the data from the underlying data store to a path
        in the filesystem. The default implementation uses the get() method
        together with chunked reads from the returned data stream to the disk.

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.

        path : string
            A file system path to store the data to.

        buffer_size : int
            An optional indicator of the number of bytes to read at a time.
            Implementations are free to ignore this hint or use a different
            default if they need to. The default is 1048576 bytes (1 MiB).
        """
        with open(path, 'wb') as fo:
            fi = self.get(key)
            while True:
                data_bytes = fi.read(buffer_size)
                if not data_bytes:
                    break
                fo.write(data_bytes)

    def from_file(self, key, path, buffer_size=1048576):
        """ Efficiently store data from a file into a key in the repository

        This method can be optionally overriden by subclasses to proved a more
        efficient way of copy the data from a path in the filesystem to the
        underlying data store. The default implementation uses the set() method
        together with chunked reads from the disk which are fed into the data
        stream.

        Parameters
        ----------
        key : string
            The key for the resource in the repository. They key is a unique
            identifier for the resource within the repository.

        path : string
            A file system path to read the data from.

        buffer_size : int
            An optional indicator of the number of bytes to read at a time.
            Implementations are free to ignore this hint or use a different
            default if they need to. The default is 1048576 bytes (1 MiB).
        """
        with open(path, 'rb') as fi:
            self.set(key, fi, buffer_size=buffer_size)
