"""兼容入口：跨店重挂 / 琴身追踪的规范实现见 instrumentdesk.instrument_registry。"""
from instrumentdesk.instrument_registry import *  # noqa: F401,F403
from instrumentdesk import instrument_registry as _canonical


def __getattr__(name):
    return getattr(_canonical, name)
