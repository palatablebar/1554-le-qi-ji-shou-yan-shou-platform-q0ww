"""兼容 service 路径，全部实现转发到 instrument_registry.service。"""
from instrumentdesk.instrument_registry.service import *  # noqa: F401,F403
from instrumentdesk.instrument_registry import service as _canonical


def __getattr__(name):
    return getattr(_canonical, name)
