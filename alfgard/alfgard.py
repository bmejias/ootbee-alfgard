#! /usr/bin/env python3

from subprocess import Popen, PIPE
from time import sleep
import os
import psycopg2
import signal
import sys

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


def print_help(exit_status):
    print("Usage: ./alfgard.py {start|stop}")
    print("Configuration on ../etc/alfgard.ini")
    sys.exit(exit_status)


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


def jmx_call(config, bean, op, props):
    props = (props,) if type(props) is str else props  # props always a tuple
    host = config['jmx']['host']
    port = config['jmx']['port']
    url = "service:jmx:rmi:///jndi/rmi://%s:%s/alfresco/jmxrmi" % (host, port)
    jmx_vars = {'java': config['jmx']['java'],
                'jmxterm': config['jmx']['jmxterm'],
                'url': url,
                'user': config['jmx']['user'],
                'password': config['jmx']['password']}
    get_values = 'echo "%s -s -b %s %s"' % (op, bean, " ".join(props))
    jmx_call = "%(java)s -jar %(jmxterm)s" % jmx_vars
    jmx_call += " -l %(url)s" % jmx_vars
    jmx_call += " -u %(user)s -p %(password)s -v silent -n" % jmx_vars
    call = '%s | %s' % (get_values, jmx_call)
    p = Popen(call, shell=True, stdout=PIPE).stdout.read()
    result = p.decode('UTF-8')
    return tuple(x for x in result.split('\n') if x is not '')


def get_db_pool_size(config):
    bean = "Alfresco:Name=ConnectionPool"
    op = "get"
    props = ("NumActive", "NumIdle")

    result = jmx_call(config, bean, op, props)
    active = int(result[0])
    idle = int(result[1])
    return (active, idle, active + idle)


def get_tomcat_threadpool(config):
    bean = "Catalina:name=tomcatThreadPool,type=Executor"
    op = "get"
    props = ("corePoolSize", "poolSize", "largestPoolSize",
             "activeCount", "queueSize")

    result = jmx_call(config, bean, op, props)
    print(result)
    return tuple(int(i) for i in result)


def monitor_db_cnxpool(config):
    cursor = connect_to_db(config)
    db_stream = open('%s.out' % config['db']['outputname'], 'w')
    db_stream.write("MIN\tCURR\tMAX\t%\tACT\tIDLE\tPOOL\tDIFF\n")
    db_stream.flush()
    while True:
        dbname = config['db']['name']
        pmin = config['db']['poolmin']
        pmax = config['db']['poolmax']
        (c, ratio) = check_db_connections(cursor, dbname, pmin, pmax)
        (active, idle, pool) = get_db_pool_size(config)
        relation = c - pool
        db_stream.write("%s\t%s\t%s\t%.1f\t%s\t%s\t%s\t%s\n" % (pmin, c, pmax,
                                                                ratio, active,
                                                                idle, pool,
                                                                relation))
        db_stream.flush()
        sleep(2)

    db_stream.close()
    sys.exit(0)


def monitor_tomcat_threadpool(config):
    while True:
        t = get_tomcat_threadpool(config)
        print("%s\t%s\t%s\t%s\t%s" % t)
        sleep(2)
    sys.exit(0)


def monitor(procedure, config, pids):
    thefork = os.fork()
    if thefork is 0:
        procedure(config)
    else:
        pids.write("%s\n" % thefork)


def main():
    config = configparser.SafeConfigParser()
    config.read('../etc/alfgard.ini')

    cmd = 'error' if len(sys.argv) is 1 else sys.argv[1]
    if cmd == 'start':
        # TODO: check if the file already exist
        pids = open('../var/alfgard.pid', 'w')
        if config['db']['check'] == 'true':
            monitor(monitor_db_cnxpool, config, pids)
        if config['tomcat']['check'] == 'true':
            monitor(monitor_tomcat_threadpool, config, pids)
        pids.close()
    elif cmd == 'stop':
        pids = open('../var/alfgard.pid', 'r')
        for line in pids:
            pid = int(line.strip())
            # TODO: what if pids are already dead?
            os.kill(pid, signal.SIGTERM)
        pids.close()  # TODO: should remove pids file after close
    elif cmd == 'help':
        print_help(0)
    else:
        print_help(1)


if __name__ == '__main__':
    main()
