"""更新用户等级：物流专员→物流仓管员"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))
from db import execute

n = execute("UPDATE user_info SET `level`='物流仓管员' WHERE `level`='物流专员'")
if n is None:
    # lastrowid返回0时不确定是否成功，用查询验证
    from db import fetch_one
    cnt = fetch_one("SELECT COUNT(*) FROM user_info WHERE `level`='物流仓管员'")
    print(f"当前物流仓管员数量: {cnt[0]}")
else:
    print(f"已更新 {n} 条记录")
