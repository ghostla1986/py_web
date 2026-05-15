# -*- coding: utf-8 -*-
"""
数据库连接工具模块
使用 PyMySQL + PooledDB 连接池管理 MySQL 连接
提供四个核心函数：fetch_one / fetch_all / execute / execute_many
"""

import pymysql
from dbutils.pooled_db import PooledDB

# 数据库连接池配置
# 同一时间最多 10 个连接，最少保持 2 个空闲连接
POOL = PooledDB(
    creator=pymysql,
    maxconnections=10,       # 连接池最大容量
    mincached=2,             # 初始化时创建的最少空闲连接数
    maxcached=5,             # 最大空闲连接数
    blocking=True,           # 无可用连接时是否阻塞等待
    setsession=[],           # 每个连接创建时执行的 SQL
    ping=0,                  # 0=不检测连接有效性
    host='192.168.2.106',
    port=3306,
    user='gzeis',
    passwd='gz007007*A',
    charset="utf8",
    db='web_mysql'
)


def _get_conn():
    """从连接池获取一个连接"""
    return POOL.connection()


def fetch_one(sql, params=None):
    """
    查询单条记录
    :param sql: SQL 语句（支持 %s 占位符）
    :param params: 参数元组或列表
    :return: 单条记录元组，无结果返回 None
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def fetch_all(sql, params=None):
    """
    查询多条记录
    :param sql: SQL 语句
    :param params: 参数元组或列表
    :return: 记录元组列表
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result


def execute(sql, params=None):
    """
    执行 INSERT / UPDATE / DELETE 操作
    :param sql: SQL 语句
    :param params: 参数元组或列表
    :return: 插入的自增 ID（INSERT 时），否则返回 0
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    conn.close()
    return last_id


def execute_many(sql, params_list):
    """
    批量执行 SQL（常用于批量插入）
    :param sql: SQL 语句
    :param params_list: 参数列表，每个元素是一个元组
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.executemany(sql, params_list)
    conn.commit()
    cur.close()
    conn.close()
