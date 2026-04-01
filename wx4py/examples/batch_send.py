"""
批量发送消息到多个群
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 使用库正式导入是这样的方式
# from wx4py import WeChatClient

# 拉取代码直接测试的话，IDE里使用这样的
from src import WeChatClient

wx = WeChatClient()
wx.connect()

results = wx.chat_window.batch_send(
    targets=["测试龙虾1", "测试龙虾2", "测试龙虾3"],
    message="通知：今晚8点开会",
    target_type='group',
)

for name, ok in results.items():
    print(f"{name}: {'成功' if ok else '失败'}")

wx.disconnect()
