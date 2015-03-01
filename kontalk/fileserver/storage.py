# -*- coding: utf-8 -*-
"""Storage modules."""
"""
  Kontalk Fileserver
  Copyright (C) 2015 Kontalk Devteam <devteam@kontalk.org>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import os

from twisted.enterprise import adbapi


try:
    from collections import OrderedDict
except:
    from ordereddict import OrderedDict

import util

dbpool = None


def init(config):
    global dbpool
    dbpool = adbapi.ConnectionPool(config['dbmodule'], host=config['host'], port=config['port'],
        user=config['user'], passwd=config['password'], db=config['dbname'], autoreconnect=True)


""" interfaces """


class NetworkStorage:
    """Network info storage."""

    def get_list(self):
        """Retrieve the list of servers in this network."""
        pass


class FileStorage:
    """File storage."""

    def init(self):
        """Initializes this storage driver."""
        pass

    def get(self, name, return_data=True):
        """Retrieves a stored file."""
        pass

    def store_file(self, name, mime, fn):
        """Stores a file reading data from a file-like object."""
        pass

    def store_data(self, name, mime, data):
        """Stores a file reading data from a string."""
        pass


""" implementations """


class MySQLNetworkStorage(NetworkStorage):

    def get_list(self):
        # WARNING accessing Twisted internals and *blocking*
        global dbpool
        conn = dbpool.connectionFactory(dbpool)
        tx = dbpool.transactionFactory(dbpool, conn)
        tx.execute('SELECT fingerprint, host, enabled FROM servers ORDER BY fingerprint')
        data = tx.fetchall()
        out = OrderedDict()
        for row in data:
            # { fingerprint: {host, enabled} }
            out[str(row[0]).upper()] = { 'host' : str(row[1]), 'enabled' : int(row[2]) }
        return out


class DiskFileStorage(FileStorage):
    """File storage."""

    def __init__(self, path):
        self.path = path

    def init(self):
        try:
            os.makedirs(self.path)
        except:
            pass

    def get(self, name, return_data=True):
        if return_data:
            # TODO
            raise NotImplementedError()
        else:
            fn = os.path.join(self.path, name)
            metafn = fn + '.properties'
            if os.path.isfile(fn) and os.path.isfile(metafn):
                # read metadata
                metadata = {}
                f = open(metafn, 'r')
                for line in f:
                    key, value = line.split('=')
                    metadata[key] = value.strip('\n')
                f.close()

                return fn, metadata['mime'], metadata['md5sum']

    def store_file(self, name, mime, fn):
        # TODO
        raise NotImplementedError()

    def store_data(self, name, mime, data):
        filename = os.path.join(self.path, name)
        f = open(filename, 'w')
        f.write(data)
        f.close()

        # calculate md5sum for file
        # this is intentionally done to verify that the file is not corruputed on disk
        # TODO this should be async
        md5sum = util.md5sum(filename)

        # write metadata file (avoid using ConfigParser, it's a simple file)
        f = open(filename + '.properties', 'w')
        f.write("mime=%s\n" % (mime, ))
        f.write("md5sum=%s\n" % (md5sum, ))
        f.close()

        return filename
