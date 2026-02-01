import pymysql
from dbutils.pooled_db import PooledDB

POOL = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    blocking=True,
    setsession=[],
    ping=0,
    host='192.168.2.106', port=3306, user='gzeis', passwd='gz007007*A', charset="utf8", db='web_mysql'
)

def _get_conn():
    return POOL.connection()

def fetch_one(sql, params=None):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def fetch_all(sql, params=None):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def execute(sql, params=None):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    conn.close()
    return last_id

def execute_many(sql, params_list):
    conn = _get_conn()
    cur = conn.cursor()
    cur.executemany(sql, params_list)
    conn.commit()
    cur.close()
    conn.close()