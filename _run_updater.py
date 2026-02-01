"""直接执行 update_status.py 的逻辑，绕开 shell 调用"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

try:
    from db import execute

    r1 = execute("UPDATE orders SET status='已配送' WHERE status='已发货'")
    print(f"已发货→已配送: 影响 {r1 if r1 is not None else 0} 行")

    r2 = execute("UPDATE orders SET status='已送达' WHERE status='已签收'")
    print(f"已签收→已送达: 影响 {r2 if r2 is not None else 0} 行")

    print("状态更新完成")
except Exception as e:
    print(f"错误: {e}")
    sys.exit(1)
