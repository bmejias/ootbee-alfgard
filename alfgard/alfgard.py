#! /usr/bin/env python3

from time import sleep
import io
import psycopg2
import subprocess
import sys

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


def get_pool_size(config):
    bean = "Alfresco:Name=ConnectionPool"
    props = "NumActive NumIdle"
    host = config['jmx']['host']
    port = config['jmx']['port']
    url = "service:jmx:rmi:///jndi/rmi://%s:%s/alfresco/jmxrmi" % (host, port)

    jmx_vars = {'java': config['jmx']['java'],
                'jmxterm': config['jmx']['jmxterm'],
                'url': url,
                'user': config['jmx']['user'],
                'password': config['jmx']['password']}
    get_values = 'echo "get -s -b %s %s"' % (bean, props)
    jmx_call = "%(java)s -jar %(jmxterm)s" % jmx_vars
    jmx_call += " -l %(url)s" % jmx_vars
    jmx_call += " -u %(user)s -p %(password)s -v silent -n" % jmx_vars
    call = '%s | %s' % (get_values, jmx_call)
    p = subprocess.Popen(call, shell=True, stdout=subprocess.PIPE).stdout.read()
    result = p.decode('UTF-8')
    values = result.split('\n')
    active = int(values[0])
    idle = int(values[1])
    return (active, idle, active + idle)


def main():
    config = configparser.SafeConfigParser()
    config.read('../etc/alfgard.ini')
    cursor = connect_to_db(config)

    db_stream = io.open(config['output']['db'], 'w')
    db_stream.write("MIN\tCURR\tMAX\t%\tACT\tIDLE\tPOOL\tDIFF\n")
    db_stream.flush()
    while True:
        dbname = config['db']['name']
        pmin = config['db']['poolmin']
        pmax = config['db']['poolmax']
        (c, ratio) = check_db_connections(cursor, dbname, pmin, pmax)
        (active, idle, pool) = get_pool_size(config)
        relation = c - pool
        db_stream.write("%s\t%s\t%s\t%.1f\t%s\t%s\t%s\t%s\n" % (pmin, c, pmax,
                                                                ratio, active,
                                                                idle, pool,
                                                                relation))
        db_stream.flush()
        sleep(2)

    db_stream.close()

if __name__ == '__main__':
    main()