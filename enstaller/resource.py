import json
from os.path import expanduser





if __name__ == '__main__':
    fi = open(expanduser('~/buildware/scripts/epd_index.json'))
    index = json.load(fi)
    fi.close()

    print index
