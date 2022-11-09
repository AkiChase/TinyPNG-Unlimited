import argparse
import json
import os
import sys
import time

from loguru import logger
from tqdm import tqdm

# 添加包路径进入环境变量
cur_file_path = sys.argv[0]
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(cur_file_path), '..')))
os.system('title=TinyPng无限制压缩图片')

from tinypng_unlimited import KeyManager, TinyImg


def init(proxy=None):
    logger.info('TinyPng正在初始化')
    KeyManager.init(os.path.dirname(cur_file_path))

    tmp_dir = os.path.join(os.path.dirname(cur_file_path), 'tmp')
    if os.path.exists(tmp_dir):
        os.removedirs(tmp_dir)  # 清空之前的临时下载文件夹

    if not len(KeyManager.Keys.available):
        logger.error('无可用密钥，请稍后重试')
        exit()

    TinyImg.set_key(KeyManager.Keys.available[0])

    if proxy is not None:
        TinyImg.set_proxy(proxy)

    logger.success('TinyPng初始化成功')


def compress_error_files(file_list):
    times = 0
    logger.warning('存在压缩失败图片({}):\n{}', len(file_list), file_list)
    while times < 5:
        times += 1
        logger.info('1s后对上述文件列表内文件进行压缩(第{}次)', times)
        time.sleep(1)
        res = TinyImg.compress_from_file_list(file_list)
        tqdm.write('')
        logger.debug('压缩报告基本信息:\n{}', json.dumps(res['basic'], ensure_ascii=False, indent=2))
        # 压缩失败文件不考虑输出日志到文件
        if res['basic']['error_count'] > 0:  # 仍然存在压缩失败的文件
            file_list = res['error_files']
            logger.warning('存在压缩失败图片({}):\n{}', len(file_list), file_list)
        else:
            return

    file_path = os.path.abspath(os.path.join(os.path.dirname(cur_file_path), 'error_files.json'))
    try:
        with open(file_path, encoding='utf-8') as f:
            old_error_files = json.load(f)
    except Exception:
        old_error_files = []
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(old_error_files + file_list, f, ensure_ascii=False, indent=2)
    logger.error('超过压缩失败重试次数{}, 压缩失败图片路径已保存', times)


def compress_cover(input_type: str, file_list: list = None, dir_path: str = None,
                   proxy: str = None, log: bool = False):
    if input_type == 'dir':
        if not len(dir_path):
            return False
    elif input_type == 'file_list':
        if not len(file_list):
            return False
    else:
        raise Exception('input_type must be "dir" or "file_list"')

    if proxy:
        logger.info('配置: 使用代理上传图片: {}', proxy)
    if log:
        logger.info('配置: 压缩完成后输出压缩日志文件')

    try:
        if input_type == 'dir':
            logger.info('1s后开始对文件夹内图片进行压缩: {}', dir_path)
            time.sleep(1)
            res = TinyImg.compress_from_dir(dir_path)
        else:
            logger.info('1s后开始对图片列表进行压缩: {}', file_list)
            time.sleep(1)
            res = TinyImg.compress_from_file_list(file_list)
        tqdm.write('')
        logger.debug('压缩报告基本信息:\n{}', json.dumps(res['basic'], ensure_ascii=False, indent=2))

        # 仅文件夹才输出日志
        if input_type == 'dir' and log:
            log_path = os.path.abspath(os.path.join(dir_path, 'log.json'))
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            logger.success('压缩日志已输出: {}', log_path)

        if res['basic']['error_count'] > 0:  # 存在压缩失败的文件
            compress_error_files(res['error_files'])

    except Exception as e:
        logger.error(e)
    return True


def compress_cover_dir(dir_path: str, proxy: str = None, log: bool = False):
    """
    压缩文件夹内图片（覆盖）
    :param dir_path: 文件夹路径
    :param proxy: 代理地址
    :param log: 是否输出日志到该文件夹
    :return: bool 是否进行了压缩
    """
    return compress_cover(input_type='dir', dir_path=dir_path, proxy=proxy, log=log)


def compress_cover_file_list(file_list: list, proxy: str = None):
    """
    压缩文件列表内图片（覆盖）
    :param file_list: 文件路径列表
    :param proxy: 代理地址
    :return: bool 是否进行了压缩
    """
    return compress_cover(input_type='file_list', file_list=file_list, proxy=proxy)


def character_drawing():
    tqdm.write(r'''
  _______             ____  _   ________   __  __      ___           _ __           __
 /_  __(_)___  __  __/ __ \/ | / / ____/  / / / /___  / (_)___ ___  (_) /____  ____/ /
  / / / / __ \/ / / / /_/ /  |/ / / __   / / / / __ \/ / / __ `__ \/ / __/ _ \/ __  / 
 / / / / / / / /_/ / ____/ /|  / /_/ /  / /_/ / / / / / / / / / / / / /_/  __/ /_/ /  
/_/ /_/_/ /_/\__, /_/   /_/ |_/\____/   \____/_/ /_/_/_/_/ /_/ /_/_/\__/\___/\__,_/   
            /____/                                                                    
    ''')


def check_error_files(proxy=None):
    path = os.path.abspath(os.path.join(os.path.dirname(cur_file_path), 'error_files.json'))
    try:
        with open(path, encoding='utf-8') as f:
            file_list = json.load(f)
    except:
        return

    if isinstance(file_list, list) and len(file_list) > 0:
        logger.info('检测到压缩失败图片路径列表, 1s后开始压缩')
        os.remove(path)
        compress_cover_file_list(file_list, proxy)
        logger.success('文件列表压缩完成')
        character_drawing()
        os.system('echo \7')  # 输出到终端时可以发出蜂鸣作为一种提醒


def command_dir(args):
    if args.dir is None:
        args.dir = input('输入图片文件夹路径(为空则结束程序):').strip('"')

    character_drawing()
    init(proxy=args.proxy)
    check_error_files(args.proxy)

    while compress_cover_dir(args.dir, args.proxy, args.log):
        tqdm.write('=' * 60)
        if args.recur:
            # 递归子文件夹
            for root, dirs, files in os.walk(args.dir):
                for dir_path in dirs:
                    dir_path = os.path.join(root, dir_path)
                    logger.info('正在递归子文件夹: {}', dir_path)
                    compress_cover_dir(dir_path, args.proxy, args.log)
                    tqdm.write('=' * 60)
        character_drawing()
        os.system('echo \7')  # 输出到终端时可以发出蜂鸣作为一种提醒
        args.dir = input('输入下一个图片文件夹路径(为空则结束程序):').strip('"')


def command_file(args):
    character_drawing()
    init(proxy=args.proxy)
    check_error_files(args.proxy)

    compress_cover_file_list([args.file], args.proxy)
    logger.success('文件压缩完成')


def command_tasks(args):
    if os.path.exists(args.path):
        with open(args.path, encoding='utf-8') as f:
            tasks = json.load(f)
    else:
        logger.error('{} does not exist', args.path)
        return

    character_drawing()
    init(proxy=args.proxy)
    check_error_files(args.proxy)

    length = 1 if 'file_tasks' in tasks else 0
    length += len(tasks['dir_tasks']) if 'dir_tasks' in tasks else 0
    with tqdm(desc='[总体进度]', unit='任务', total=length, file=sys.stdout, ascii=' ▇',
              colour='magenta', leave=False, ncols=120, position=5) as bar:
        if 'file_tasks' in tasks:
            compress_cover_file_list(tasks['file_tasks'], args.proxy)
            logger.success('文件列表压缩完成')
            bar.update()
            character_drawing()
            os.system('echo \7')  # 输出到终端时可以发出蜂鸣作为一种提醒
        if 'dir_tasks' in tasks:
            for dir_task in tasks['dir_tasks']:
                compress_cover_dir(dir_task, args.proxy, args.log)
                if args.recur:
                    # 递归子文件夹
                    for root, dirs, files in os.walk(dir_task):
                        for dir_path in dirs:
                            dir_path = os.path.join(root, dir_path)
                            logger.info('正在递归子文件夹: {}', dir_path)
                            compress_cover_dir(dir_path, args.proxy, args.log)
                logger.success('文件夹列表压缩完成')
                tqdm.write('=' * 60)
                bar.update()
            character_drawing()
        os.system('echo \7')  # 输出到终端时可以发出蜂鸣作为一种提醒
    tqdm.write('')


def command_apply(args):
    KeyManager.working_dir = os.path.dirname(cur_file_path)
    KeyManager.load_keys()
    KeyManager.apply_store_key(args.num)


def command_rearrange(args):
    KeyManager.working_dir = os.path.dirname(cur_file_path)
    KeyManager.rearrange_keys()


def main():
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='Tinify Your Images Unlimited! '
                                                 'All compressed images will cover themselves.')
    subparsers = parser.add_subparsers(metavar='<command>')
    # dir
    dir_parser = subparsers.add_parser('dir', help='Compress images from dir or input the path later')
    dir_parser.add_argument('-d', '--dir', type=str, help='The dir where your images are.')
    dir_parser.set_defaults(func=command_dir)
    # file
    file_parser = subparsers.add_parser('file', help='Compress image from file')
    file_parser.add_argument('file', type=str, help='The path where the image is.')
    file_parser.add_argument('-p', '--proxy', type=str, help='The proxy used on uploading images.')
    file_parser.set_defaults(func=command_file)
    # tasks
    tasks_parser = subparsers.add_parser('tasks', help='Compress images from tasks.json')
    tasks_parser.add_argument('path', type=str, help='The path where the tasks.json is.')
    tasks_parser.set_defaults(func=command_tasks)

    for p in dir_parser, tasks_parser:
        p.add_argument('-p', '--proxy', type=str, help='The proxy used on uploading images.')
        p.add_argument('-r', '--recur', action='store_true', help='Whether to recurse the dir.')
        p.add_argument('-l', '--log', action='store_true', help='Whether to output compression log in images dir.')

    # apply
    apply_parser = subparsers.add_parser('apply', help='Apply TinyPNG API key.')
    apply_parser.add_argument('num', type=int, nargs='?', default=4,
                              help='The number of times to apply a TinyPNG API key.')
    apply_parser.set_defaults(func=command_apply)

    # rearrange
    apply_parser = subparsers.add_parser('rearrange',
                                         help='Rearrange API keys in keys.json by compression count.')
    apply_parser.set_defaults(func=command_rearrange)

    args = parser.parse_args()
    if 'func' not in args:
        parser.print_help()
        return
    args.func(args)
    input('回车退出')


if __name__ == '__main__':
    main()
