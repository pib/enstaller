import json
from os.path import dirname, expanduser

from indexed_repo.chain import Chain



if __name__ == '__main__':
    path = expanduser('~/buildware/scripts/index.json')
    fi = open(path)
    index = json.load(fi)
    fi.close()
    index['url'] = 'file://%s/' % dirname(path)

    c = Chain([index], verbose=1)
