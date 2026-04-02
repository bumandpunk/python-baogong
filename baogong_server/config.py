# -*- coding: utf-8 -*-
"""
报工服务配置
"""
import os

# ==================== 服务配置 ====================
SERVER_HOST = os.environ.get("BAOGONG_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("BAOGONG_PORT", "8000"))

# 发送重试
SEND_RETRY_COUNT = int(os.environ.get("BAOGONG_SEND_RETRY_COUNT", "2"))   # 失败后重试次数
SEND_RETRY_DELAY = float(os.environ.get("BAOGONG_SEND_RETRY_DELAY", "2.0"))  # 重试间隔（秒）

# 超时保护
REQUEST_TIMEOUT_COMPOSE = int(os.environ.get("BAOGONG_TIMEOUT_COMPOSE", "30"))  # 图片合成超时（秒）
REQUEST_TIMEOUT_SEND = int(os.environ.get("BAOGONG_TIMEOUT_SEND", "60"))        # 微信发送超时（秒）

# 防抖：同一报工请求在窗口期内重复调用直接返回，不重复发送
# 防抖 key = (report_type, reporter, group_name, date_str)，窗口内完全相同的请求视为重复
DEBOUNCE_WINDOW = int(os.environ.get("BAOGONG_DEBOUNCE_WINDOW", "20"))  # 防抖窗口（秒），0 表示禁用

# 微信进程保活
WECHAT_PROCESS_NAME = os.environ.get("BAOGONG_WX_PROCESS", "WeChat.exe")
# 微信可执行文件路径，留空则自动在常见路径查找
WECHAT_EXE_PATH = os.environ.get("BAOGONG_WX_EXE", "")
# 微信启动后等待就绪的秒数
WECHAT_LAUNCH_WAIT = int(os.environ.get("BAOGONG_WX_LAUNCH_WAIT", "8"))
# 连接失败时是否尝试自动启动微信进程（仅 Windows）
WECHAT_AUTO_LAUNCH = os.environ.get("BAOGONG_WX_AUTO_LAUNCH", "true").lower() == "true"

# ==================== 画布参数 ====================
CANVAS_WIDTH = 1080          # 画布固定宽度（px）
CANVAS_BG_COLOR = (255, 255, 255)  # 白色背景

# 各区块内边距
PADDING = 24                 # 全局内边距（px）
SECTION_GAP = 0              # 区块间距（px）

# 标题区
TITLE_HEIGHT = 160           # 标题区高度（px）
TITLE_TEXT = "报  工"
TITLE_FONT_SIZE = 80
TITLE_COLOR = (176, 23, 31)  # 深红色 #B0171F
TITLE_BORDER_COLOR = (176, 23, 31)
TITLE_BORDER_WIDTH = 3
TITLE_INNER_BORDER_GAP = 6   # 内外框间距

# 信息栏
INFO_BAR_HEIGHT = 80
INFO_FONT_SIZE = 38
INFO_BG_COLOR = (255, 255, 255)
INFO_TEXT_COLOR = (30, 30, 30)
INFO_BORDER_COLOR = (176, 23, 31)
INFO_BORDER_WIDTH = 2

# 图片网格
GRID_COLS = 3                # 每行列数
GRID_GAP = 6                 # 图片间距（px）
GRID_ASPECT = (4, 3)         # 单格宽高比（宽:高）

# 底部品牌区
FOOTER_PADDING_V = 36        # 底部区上下内边距
FOOTER_FONT_SIZE = 30
FOOTER_BG_COLOR = (245, 245, 245)
FOOTER_TEXT_COLOR = (80, 80, 80)
FOOTER_LINE1 = "捷租先登出品"
FOOTER_LINE2 = "本次报工由门神域系统自动上报"
FOOTER_LINE_GAP = 14         # 两行之间间距

# ==================== Logo 配置 ====================
import pathlib as _pathlib
_ASSETS_DIR = _pathlib.Path(__file__).parent / "assets"
# Logo 图片路径，放在 baogong_server/assets/logo.png
LOGO_PATH = str(_ASSETS_DIR / "logo.png")
LOGO_SIZE = 80           # logo 在标题区左上角的高度（px），宽度等比缩放
LOGO_MARGIN = 16         # logo 距左边和上边的距离（px）

# ==================== 字体配置 ====================
# 优先顺序：环境变量 > Windows系统字体 > 备用字体 > Pillow默认字体
_FONT_CANDIDATES = [
    os.environ.get("BAOGONG_FONT_PATH", ""),
    r"C:\Windows\Fonts\msyh.ttc",                           # 微软雅黑（Windows）
    r"C:\Windows\Fonts\simhei.ttf",                         # 黑体（Windows备用）
    r"C:\Windows\Fonts\simsun.ttc",                         # 宋体（Windows备用）
    "/System/Library/Fonts/STHeiti Medium.ttc",             # macOS 华文黑体
    "/System/Library/Fonts/STHeiti Light.ttc",              # macOS 华文黑体 Light
    "/System/Library/Fonts/Hiragino Sans GB.ttc",           # macOS 冬青黑体简体
    "/System/Library/PrivateFrameworks/FontServices.framework/Versions/A/Resources/Reserved/PingFangUI.ttc",  # macOS PingFang
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",        # Linux备用
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto
]

def get_font_path() -> str:
    """获取可用的中文字体路径，找不到则返回空字符串（使用Pillow默认字体）"""
    for path in _FONT_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return ""

FONT_PATH = get_font_path()
