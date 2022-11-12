import json
import os
import re
import time

import requests
from loguru import logger
from requests import Timeout

from tinypng_unlimited.errors import SnapMailException, ApplyKeyException
from tinypng_unlimited.snapmail import SnapMail


class KeyManager:
    working_dir: str

    class Keys:
        available: list
        unavailable: list

        @classmethod
        def load(cls, obj: dict):
            cls.available = obj['available'] if 'available' in obj else []
            cls.unavailable = obj['unavailable'] if 'unavailable' in obj else []

    @classmethod
    def init(cls, working_dir):
        """
        密钥初始化，请在所有需要密钥的操作之前执行
        """
        cls.working_dir = working_dir
        cls.load_keys()
        if len(cls.Keys.available) < 3:
            logger.warning('当前可用密钥少于3条，优先申请新密钥')
            cls.apply_store_key()

    @classmethod
    def load_keys(cls):
        """
        加载本地存储的密钥
        """
        path = os.path.abspath(os.path.join(cls.working_dir, 'keys.json'))
        if not os.path.exists(path):
            cls.Keys.load({})
        else:
            with open(path, 'r', encoding='utf-8') as f:
                cls.Keys.load(json.load(f))

    @classmethod
    def store_key(cls):
        """
        密钥保存到本地
        """
        path = os.path.abspath(os.path.join(cls.working_dir, 'keys.json'))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                "available": cls.Keys.available,
                "unavailable": cls.Keys.unavailable
            }, f, ensure_ascii=False, indent=4, separators=(',', ':'))

    @staticmethod
    def get_api_count(s, key):
        url = 'https://api.tinify.com/shrink'
        retry = 0
        logger.info('正在获取密钥可用性信息... : {}', key)
        while True:
            try:
                res = s.post(url, auth=('api', key))
                return int(res.headers.get('compression-count'))
            except Exception as e:
                retry += 1
                if retry > 3:  # 最多再重试3次（总共4次）
                    raise e
                time.sleep(1)

    @classmethod
    def rearrange_keys(cls):
        path = os.path.abspath(os.path.join(cls.working_dir, 'keys.json'))
        if not os.path.exists(path):
            keys = {"available": [], "unavailable": []}
        else:
            with open(path, 'r', encoding='utf-8') as f:
                keys = json.load(f)
        out = {"available": [], "unavailable": []}

        with requests.Session() as s:
            for type_name in ('available', 'unavailable'):
                for index, key in enumerate(keys[type_name]):
                    count = cls.get_api_count(s, key)
                    out['available' if count < 490 else 'unavailable'].append((keys[type_name][index], count))

        for type_name in ('available', 'unavailable'):
            out[type_name].sort(key=lambda item: item[1], reverse=True)
            logger.info('统计信息:', type_name)
            logger.info(json.dumps(out[type_name], indent=2))
            out[type_name] = [x[0] for x in out[type_name]]

        cls.Keys.load(out)
        cls.store_key()
        logger.success('密钥已按统计信息重新排列')

    @classmethod
    def next_key(cls) -> str:
        """
        删除当前密钥并返回下一条
        """
        cls.load_keys()

        if len(cls.Keys.available) < 3:
            logger.warning('可用密钥少于3条，优先申请新密钥')
            cls.apply_store_key()

        if not len(cls.Keys.available):
            raise Exception('无可用密钥，请申请后重试')
        cls.Keys.unavailable.append(cls.Keys.available.pop(0))
        cls.store_key()
        logger.debug('密钥已切换，等待载入')
        return cls.Keys.available[0]

    @classmethod
    def _apply_api_key(cls) -> str:
        """
        申请新密钥
        """
        with requests.Session() as session:
            # 注册新账号（发送确认邮件）
            mail = SnapMail.create_new_mail()
            res = session.post('https://tinypng.com/web/api', json={
                "fullName": mail[:mail.find('@')],
                "mail": mail
            })

            if res.status_code == 429:
                raise ApplyKeyException('新账号注册过于频繁', res.text)
            if res.status_code != 200 or res.text != '{}':
                raise ApplyKeyException('新账号注册未知错误', res.text)
            logger.info('注册邮件已发送至:{}', mail)
            time.sleep(5)  # 5s后开始

            # 接收邮件，提取链接
            try:
                res_json: dict = SnapMail.get_email_list(session, 1)
                match = re.search(r'(https://tinify.com/login\?token=.*?api)', res_json[0]['text'])
                url = match.group(1)
            except SnapMailException as e:
                raise ApplyKeyException('注册邮件接收失败', e)
            except Exception as e:
                raise ApplyKeyException('注册链接提取失败', e)
            logger.info('注册链接提取成功')

            # 访问控制台，生成密钥
            retry = 0
            while True:
                try:
                    session.get(url)
                    auth = (session.get('https://tinify.com/web/session')).json()['token']  # 获取鉴权
                    headers = {
                        'authorization': f"Bearer {auth}"
                    }
                    session.post('https://api.tinify.com/api/keys', headers=headers)  # 添加新密钥
                    res = session.get('https://api.tinify.com/api', headers=headers)  # 获取密钥
                    key = res.json()['keys'][-1]['key']
                    break
                except Exception as e:
                    retry += 1
                    if retry <= 3:
                        logger.error('新密钥生成失败, 3s后进行第{}次重试 {}', retry, e)
                        time.sleep(3)
                    else:
                        raise ApplyKeyException(f'超出重试次数, 新密钥生成失败: {url}', e)

            logger.success('新密钥生成成功')
            return key

    @classmethod
    def apply_store_key(cls, times=None):
        """
        申请并保存密钥
        """

        # 允许申请次数（包括失败重试）
        times = 4 - len(cls.Keys.available) if times is None else times
        while times > 0:
            try:
                times -= 1
                logger.info('正在申请新密钥，剩余次数: {}', times)
                key = cls._apply_api_key()
                cls.Keys.available.append(key)
                cls.store_key()
            except Timeout as e:
                logger.error("请求超时: {} - {}({})", e.request.method, e.request.url, bytes.decode(e.request.content))
            except Exception as e:
                logger.error(e)
