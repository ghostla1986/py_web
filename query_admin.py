import sys
sys.path.insert(0, 'utils')
from db import fetch_one

r = fetch_one('SELECT user, pwd, level FROM user_info WHERE level=%s', ('管理员',))
print(r)
