#! /usr/bin/env python3

import sys
import psycopg2

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


def connect_to_db(config):
    try:
        conn = psycopg2.connect(host=config['db']['host'],
                                port=config['db']['port'],
                                database=config['db']['name'],
                                user=config['db']['username'],
                                password=config['db']['password'])
        return conn.cursor()
    except psycopg2.Error as e:
        print("ERROR: Could not connect to database")
        print(e)
        sys.exit(1)


def main():
    config = configparser.SafeConfigParser()
    print(config)
    config.read('alfgard.ini')
    cursor = connect_to_db(config)
    cursor.execute('select version();')
    print(cursor.fetchall())
    print(sys.argv[0])


if __name__ == '__main__':
    main()
