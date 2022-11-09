import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from shutil import move
from threading import RLock

import tinify
from loguru import logger
from requests import Session
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

import tinypng_unlimited  # 不使用from import防止交叉引用
from tinypng_unlimited.errors import CompressException


class TinyImg:
    _lock: RLock = RLock()
    _session: Session = Session()
    tmp_dir: str

    @classmethod
    def set_key(cls, key):
        """
        设置新密钥并进行验证
        """

        with cls._lock:  # 加锁避免多个线程尝试切换密钥
            cls.tmp_dir = os.path.abspath(os.path.join(tinypng_unlimited.KeyManager.working_dir, 'tmp'))
            logger.debug('正在载入密钥: {}', key)
            tinify.key = key
            tinify.validate()
            logger.success('密钥已载入，当前密钥可用性: [{}/500]', cls.compression_count())
            cls.check_compression_count()

    @classmethod
    def set_proxy(cls, proxy):
        tinify.proxy = proxy

    @classmethod
    def to_file_save(cls, path, url, timeout=30):
        """
        安全的下载文件并保存到指定路径
        :param path: 路径
        :param url: 图片下载链接
        :param timeout: 下载超时
        """
        file_name = os.path.basename(path)
        if not os.path.exists(cls.tmp_dir):
            os.mkdir(cls.tmp_dir)
        tmp_path = os.path.abspath(os.path.join(cls.tmp_dir, f'{file_name}_{round(time.time())}'))
        res = cls._session.get(url, stream=True, timeout=timeout)
        file_size = int(res.headers.get('content-length', 0))
        with tqdm(file=sys.stdout, desc=f'[下载进度]: {file_name}', colour='red', ncols=120, leave=False,
                  ascii=' ▇', total=file_size, unit="B", unit_scale=True, unit_divisor=1024) as bar:
            with open(tmp_path, 'wb') as f:
                wrapped_file = CallbackIOWrapper(bar.update, f, 'write')
                for data in res.iter_content(2048):
                    wrapped_file.write(data)
                f.write(b'tiny')
                logger.info('已为图片添加压缩标记tiny: {}', file_name)
            move(tmp_path, path)

    @classmethod
    def compression_count(cls) -> int:
        """
        api调用次数
        """
        with cls._lock:
            if tinify.compression_count is None:
                tinify.validate()
            return tinify.compression_count

    @classmethod
    def check_compression_count(cls):
        """
        检测密钥是否限额，限额则替换为下一条
        """
        count = cls.compression_count()
        # logger.debug('当前密钥可用性: [{}/500]', count)
        if count >= 490:  # 即将达到限额，更换新密钥（多线程，提前留好余量）
            logger.warning('当前密钥即将达到限额: [{}/500], 正在切换新密钥', count)
            cls.set_key(tinypng_unlimited.KeyManager.next_key())

    @classmethod
    def check_if_compressed(cls, path) -> bool:
        """
        检验图片是否被本程序标记为压缩
        """
        with open(path, 'rb') as f:
            f.seek(-4, 2)
            return f.read(4) == b'tiny'

    @classmethod
    def upload_from_file(cls, f, timeout=60) -> str:
        """
        重写库方法添加超时参数，上传图片，返回云端压缩后图片链接
        :param timeout: 服务器响应超时时间，注意此时间在每次服务器做出任何响应时重置，所以不是整个请求和响应的时间
        :param f: 文件对象
        """
        s: Session = tinify.get_client().session
        res = s.post('https://api.tinify.com/shrink', data=f, timeout=timeout)
        count = res.headers.get('compression-count')
        tinify.compression_count = int(count)
        return res.headers.get('location')

    @classmethod
    def compress_from_file(cls, path, new_path, check_compressed=True,
                           upload_timeout=None, download_timeout=None) -> tuple:
        """
        压缩图片文件
        :param path: 文件路径
        :param new_path: 新文件路径
        :param check_compressed: 是否检查压缩标记
        :param upload_timeout: 上传响应超时时间，默认60s
        :param download_timeout: 下载响应超时时间，默认30s
        :return: (旧大小，新大小，压缩到原来的百分比)
        """
        old_size = os.path.getsize(path)
        file_name = os.path.basename(path)
        if check_compressed and cls.check_if_compressed(path):
            logger.info('图片已带有压缩标记，不做压缩处理: {}', file_name)
            time.sleep(0.5)  # 似乎返回值太快会对多线程任务造成影响
            return file_name, old_size, old_size, '100.0%'

        retry = 0
        while True:
            try:
                # 加锁保证只有一个线程能进行检查（避免多线程同时检查，同时切换api）
                # 但是切换密钥会中断其他请求，因为tinify库中是共享同一个client
                with cls._lock:
                    cls.check_compression_count()  # 检验压缩次数是否足够
                    old_key = tinify.key
                with tqdm(file=sys.stdout, desc=f'[上传进度]: {file_name}', colour='green', ncols=120, leave=False,
                          ascii=' ▇', total=old_size, unit="B", unit_scale=True, unit_divisor=1024) as bar:
                    logger.info('正在上传图片至云端压缩[{}]: {}', cls._byte_converter(old_size), file_name)
                    with open(path, "rb") as f:
                        wrapped_file = CallbackIOWrapper(bar.update, f, "read")
                        url = cls.upload_from_file(wrapped_file, timeout=upload_timeout)
                    # 上传完成得到图片链接，并更新了api调用次数
                    with cls._lock:
                        # 新旧密钥切换时，使用旧密钥上传图片的响应会覆盖新密钥的值，所以需要刷新一下
                        if tinify.key != old_key:
                            tinify.validate()
                        logger.success('云端压缩成功，正在下载: {}', file_name)
                        logger.info('当前密钥可用性: [{}/500]', cls.compression_count())
                cls.to_file_save(new_path, url, timeout=download_timeout)
                new_size = os.path.getsize(new_path)
                return file_name, old_size, new_size, f'{round(100 * new_size / old_size, 2)}%'
            except Exception as e:
                retry += 1
                if retry <= 3:
                    logger.warning('重试压缩图片(第{}次): {}, 错误信息: {}', retry, file_name, e)
                else:
                    raise CompressException('超出压缩重试次数', {'path': path, 'err': e})

    @classmethod
    def compress_from_file_list(cls, file_list, new_dir=None, upload_timeout=None, download_timeout=None) -> dict:
        """
        批量压缩多个文件
        :param file_list: 文件路径列表
        :param new_dir: 输出文件夹
        :param upload_timeout: 上传响应超时时间，默认60s
        :param download_timeout: 下载响应超时时间，默认30s
        :return: 压缩情况报告
        """

        if new_dir and not os.path.exists(new_dir):
            os.makedirs(new_dir)

        success_count = 0
        old_size = new_size = 0  # python不用担心大数运算溢出问题
        error_files, success_files = [], []
        file_num = len(file_list)

        logger.info('待压缩图片数量: {}', file_num)

        thread_num = 4
        # 4核心理论可以8线程，但是上传速度才是决速步
        with ThreadPoolExecutor(thread_num) as pool:
            with tqdm(desc='[任务进度]', unit='份', total=file_num, file=sys.stdout, ascii=' ▇',
                      colour='yellow', leave=False, ncols=120, position=thread_num) as bar:
                future_list = []
                for old_path in file_list:
                    file_name = os.path.basename(old_path)
                    # 默认下覆盖原文件
                    new_path = os.path.abspath(os.path.join(new_dir, file_name)) if new_dir else old_path
                    future_list.append(pool.submit(cls.compress_from_file, old_path, new_path,
                                                   upload_timeout, download_timeout))

                for future in as_completed(future_list):
                    try:
                        info = future.result()
                        # 压缩成功则统计信息
                        old_size += info[1]
                        new_size += info[2]
                        success_count += 1
                        success_files.append(
                            (info[0], cls._byte_converter(info[1]), cls._byte_converter(info[2]), info[3])
                        )
                        logger.success('图片压缩完成: {}', info[0])
                    except CompressException as e:
                        error_files.append(e.detail['path'])
                        logger.error('压缩图片失败: {} {}', os.path.basename(e.detail['path']), e)
                    except Exception as e:
                        logger.error('压缩图片未知错误 {}', e)
                    bar.update()
                bar_info = bar.format_dict

        compression = f'{round(100 * new_size / old_size, 2)}%' if old_size else '100%'
        return {
            'basic': {
                'file_num': file_num, 'success_count': success_count,
                'error_count': len(error_files),
                'time': '{:.2f} s'.format(bar_info['elapsed']), 'speed': '{:.2f} 份/s'.format(bar_info['rate']),
                'output_size': cls._byte_converter(new_size), 'input_size': cls._byte_converter(old_size),
                'compression': compression, 'output_dir': '覆盖原文件' if new_dir is None else new_dir,
            },
            'error_files': error_files,
            'success_files': success_files,
        }

    @classmethod
    def compress_from_dir(cls, dir_path, new_dir=None, reg=r'.*\.(jpe?g|png|svga)$') -> dict:
        """
        压缩文件夹内图片
        :param dir_path: 文件夹路径
        :param new_dir: 输出路径(None则覆盖原文件)
        :param reg: 文件名正则匹配
        :return: 压缩情况报告
        """
        if not os.path.exists(dir_path):
            raise CompressException('源文件夹不存在', dir_path)

        # 默认覆盖原文件
        if new_dir and not os.path.exists(new_dir):
            os.makedirs(new_dir)

        file_list = [os.path.abspath(os.path.join(dir_path, f)) for f in os.listdir(dir_path) if
                     re.match(reg, f, re.IGNORECASE)]

        if not len(file_list):
            raise CompressException('文件夹内无任何匹配文件', dir_path)

        res = cls.compress_from_file_list(file_list, new_dir)
        res['input_dir'] = dir_path
        return res

    @staticmethod
    def _byte_converter(byte_num) -> str:
        if byte_num < 1024:  # 比特
            return '{:.2f} B'.format(byte_num)  # 字节
        elif 1024 <= byte_num < 1024 * 1024:
            return '{:.2f} KB'.format(byte_num / 1024)  # 千字节
        else:
            return '{:.2f} MB'.format(byte_num / 1024 / 1024)  # 兆字节
