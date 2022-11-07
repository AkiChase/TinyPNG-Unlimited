import asyncio
import json
import os
import sys
from requests import Session

os.system('title=TinyPng秘钥检验重排')


def load_keys(path):
    if not os.path.exists(path):
        return {"available": [], "unavailable": []}

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def store_keys(path, keys):
    with open(path, 'w', encoding='utf-8') as f:
        return json.dump(keys, f, indent=2)


def get_api_count(s, key):
    url = 'https://api.tinify.com/shrink'
    retry = 0
    print('正在获取秘钥可用性信息...', key)
    while True:
        try:
            res = s.post(url, auth=('api', key))
            return int(res.headers.get('compression-count'))
        except Exception as e:
            retry += 1
            if retry > 3:  # 最多再重试3次（总共4次）
                raise Exception(e)
            await asyncio.sleep(1)


async def rearrange_keys(path, co=True):
    keys = load_keys(path)
    out = {"available": [], "unavailable": []}

    with Session() as s:
        for type_name in ('available', 'unavailable'):
            for index, key in enumerate(keys[type_name]):
                count = get_api_count(s, key)
                out['available' if count < 490 else 'unavailable'].append((keys[type_name][index], count))

    for type_name in ('available', 'unavailable'):
        out[type_name].sort(key=lambda item: item[1], reverse=True)
        print('统计信息:', type_name)
        print(json.dumps(out[type_name], indent=2))
        out[type_name] = [x[0] for x in out[type_name]]

    store_keys(path, out)
    print('秘钥已按统计信息重新排列')
    input('回车退出')


if __name__ == '__main__':
    asyncio.run(rearrange_keys('keys.json', len(sys.argv) == 1))
