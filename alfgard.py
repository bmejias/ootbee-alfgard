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


def count_db_connections(cursor, dbname):
    cursor.execute(
        """SELECT count(*) FROM pg_stat_activity WHERE datname=%s
            AND pid <> pg_backend_pid()""", (dbname,))
    return cursor.fetchone()[0]


def check_db_connections(cursor, dbname, pmin, pmax):
    c = count_db_connections(cursor, dbname)
    ratio = 100.0 * c / float(pmax)
    print("Min\tCur\tMax\t%")
    print("%s\t%s\t%s\t%.1f" % (pmin, pmax, c, ratio))


def main():
    config = configparser.SafeConfigParser()
    config.read('alfgard.ini')
    cursor = connect_to_db(config)
    check_db_connections(cursor, config['db']['name'],
                         config['db']['poolmin'], config['db']['poolmax'])


if __name__ == '__main__':
    main()
