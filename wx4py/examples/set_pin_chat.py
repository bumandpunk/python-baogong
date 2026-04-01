"""
置顶 / 取消置顶聊天
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用库正式导入是这样的方式
# from wx4py import WeChatClient

# 拉取代码直接测试的话，IDE里使用这样的
from src import (WeChatClient)

wx = WeChatClient()
wx.connect()

wx.group_manager.set_pin_chat("测试龙虾1", enable=True)

wx.disconnect()
