import os
import sys

# 添加包路径进入环境变量
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'tinypng')))
os.system('title=TinyPng申请秘钥')

from tinypng_unlimited import KeyManager


def main():
    KeyManager.init(os.path.dirname(__file__))
    KeyManager.apply_store_key(4)
    input('回车退出')


if __name__ == '__main__':
    main()
