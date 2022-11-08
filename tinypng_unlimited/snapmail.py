import time
from random import sample
from loguru import logger
from requests import Session

from tinypng_unlimited.errors import SnapMailException


class SnapMail:
    BASE_URL = 'https://www.snapmail.cc/'
    mail: str = None

    @classmethod
    def create_new_mail(cls) -> str:
        cls.mail = ''.join(sample('zyxwvutsrqponmlkjihgfedcba', 16)) + '@snapmail.cc'
        return cls.mail

    @classmethod
    def session_get(cls, session: Session, url: str, params: dict = None) -> dict:
        if cls.mail is None:
            cls.create_new_mail()

        retry = 0
        while True:
            res = session.get(cls.BASE_URL + url.strip('/'), params=params)
            if res.status_code != 200:
                try:
                    err = res.json()['error']
                    if err.find('Email was not found') > -1:
                        raise SnapMailException('邮箱内无任何邮件', err)
                    elif err.find('Please try again') > -1:
                        raise SnapMailException('邮箱请求过频繁', err)
                    # 其他错误
                    logger.error(err)
                except SnapMailException as e:
                    # 明确错误
                    err = e
                    logger.error(err)
                except Exception:
                    # 未知错误
                    err = res.text
                    logger.error('未知邮箱请求错误 {}', err)

                retry += 1
                if retry <= 3:
                    logger.info(f'等待10s后进行第{retry}次重试')
                    time.sleep(10)
                else:
                    raise SnapMailException('超过重试次数', 3)
            else:
                # 状态码200则返回
                return res.json()

    @classmethod
    def get_email_list(cls, session: Session, count: int = None):
        return cls.session_get(session, f'emailList/{cls.mail}', count if count is None else {'count': count})
