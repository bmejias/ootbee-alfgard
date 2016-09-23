#! /usr/bin/env python3

from time import sleep
import io
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
    return (c, ratio)


def get_pool_size(username, password):
    return 42


def main():
    config = configparser.SafeConfigParser()
    config.read('alfgard.ini')
    cursor = connect_to_db(config)

    db_stream = io.open(config['output']['db'], 'w')
    while True:
        dbname = config['db']['name']
        pmin = config['db']['poolmin']
        pmax = config['db']['poolmax']
        (c, ratio) = check_db_connections(cursor, dbname, pmin, pmax)
        pool = get_pool_size(config['jmx']['user'], config['jmx']['password'])
        relation = c - pool
        db_stream.write("%s;%s;%s;%.1f;%s;%s\n" % (pmin, c, pmax, ratio, pool,
                                                   relation))
        db_stream.flush()
        sleep(2)

    db_stream.close()

if __name__ == '__main__':
    main()
