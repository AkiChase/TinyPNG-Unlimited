__all__ = ['TinyImg', 'KeyManager']

from loguru import logger
from tqdm import tqdm

# 避免冲突
logger.remove()
logger.add(lambda msg: tqdm.write(msg, end=''), colorize=True,
           format='<level>{time:YYYY-MM-DD HH:mm:ss}\t| {level:9}| {message}</level>')

from tinypng_unlimited.tiny_img import TinyImg
from tinypng_unlimited.key_manager import KeyManager
