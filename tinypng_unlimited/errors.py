from typing import Any


class CustomException(Exception):
    """
    自定义异常基类
    """

    def __init__(self, name: str, msg: str, detail: Any = None):
        super().__init__(name, msg, detail)
        self.msg = msg
        self.detail = detail


class SnapMailException(CustomException):
    """
    接受邮件相关错误
    """

    def __init__(self, msg: str, detail: Any = None):
        super().__init__('接受邮件相关错误', msg, detail)


class ApplyKeyException(CustomException):
    """
    申请新密钥相关错误
    """

    def __init__(self, msg: str, detail: Any = None):
        super().__init__('申请新密钥相关错误', msg, detail)


class ProxyManagerException(CustomException):
    """
    调用代理相关错误
    """

    def __init__(self, msg: str, detail: Any = None):
        super().__init__('调用代理相关错误', msg, detail)


class CompressException(CustomException):
    """
    压缩图片相关错误
    """

    def __init__(self, msg: str, detail: Any = None):
        super().__init__('压缩图片相关错误', msg, detail)
