# -*- coding: utf-8 -*-
"""
微信发送封装模块

单例管理 WeChatClient 连接，使用 asyncio.Lock 串行化发送操作（微信 UIAutomation 不线程安全），
合成图片写入临时文件后发送，发送完成立即删除临时文件。

进程保活：连接失败时自动检测微信进程是否存在，不存在则尝试启动，
          启动后等待就绪再重连（需微信已配置自动登录）。
"""
import asyncio
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# 将 wx4py 项目加入 sys.path，使 baogong_server 可以在任意工作目录运行
_WX4PY_ROOT = Path(__file__).parent.parent / "wx4py"
if str(_WX4PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_WX4PY_ROOT))


def _get_config():
    from baogong_server import config
    return config


def _import_wechat_client():
    """延迟导入 WeChatClient，避免在非 Windows 环境下启动时报错。"""
    try:
        from src import WeChatClient  # noqa
        return WeChatClient
    except ImportError as e:
        logger.warning(f"WeChatClient 导入失败（可能不在 Windows 环境）: {e}")
        return None


# ==================== 进程保活工具函数 ====================

def _is_wechat_running(process_name: str) -> bool:
    """检测微信进程是否正在运行（仅 Windows）。"""
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and proc.info["name"].lower() == process_name.lower():
                return True
        return False
    except Exception as e:
        logger.warning(f"psutil 检测进程失败: {e}")
        return False


def _find_wechat_exe() -> str:
    """在常见安装路径中查找微信可执行文件。"""
    candidates = [
        r"C:\Program Files\Tencent\WeChat\WeChat.exe",
        r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Tencent\WeChat\WeChat.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), r"Tencent\WeChat\WeChat.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def _launch_wechat(cfg) -> bool:
    """
    尝试启动微信进程。

    Returns:
        bool: 是否成功找到并启动微信
    """
    exe_path = cfg.WECHAT_EXE_PATH or _find_wechat_exe()
    if not exe_path:
        logger.error("未找到微信可执行文件，请设置环境变量 BAOGONG_WX_EXE")
        return False

    if not os.path.exists(exe_path):
        logger.error(f"微信可执行文件不存在: {exe_path}")
        return False

    try:
        logger.info(f"正在启动微信: {exe_path}")
        subprocess.Popen([exe_path], creationflags=subprocess.DETACHED_PROCESS)
        wait_sec = cfg.WECHAT_LAUNCH_WAIT
        logger.info(f"等待微信启动就绪（{wait_sec}s）...")
        time.sleep(wait_sec)
        return True
    except Exception as e:
        logger.error(f"启动微信失败: {e}")
        return False


def _ensure_wechat_process(cfg) -> bool:
    """
    确保微信进程存在，不存在时尝试自动启动。

    Returns:
        bool: 微信进程是否可用
    """
    if not cfg.WECHAT_AUTO_LAUNCH:
        return True  # 未启用保活，直接放行由后续连接逻辑处理

    if _is_wechat_running(cfg.WECHAT_PROCESS_NAME):
        return True

    logger.warning(f"未检测到微信进程（{cfg.WECHAT_PROCESS_NAME}），尝试自动启动...")
    launched = _launch_wechat(cfg)
    if launched:
        # 再次确认进程已起来
        if _is_wechat_running(cfg.WECHAT_PROCESS_NAME):
            logger.info("微信进程已启动")
            return True
        else:
            logger.error("微信进程启动后仍未检测到，可能启动失败")
            return False
    return False


# ==================== WeChatSender ====================

class WeChatSender:
    """
    单例微信发送器。

    首次调用 get_instance() 时创建实例，后续复用同一连接。
    """

    _instance: Optional["WeChatSender"] = None
    _instance_lock = asyncio.Lock()

    def __init__(self):
        self._wx = None
        self._send_lock = asyncio.Lock()
        self._connected = False

    # ==================== 单例 ====================

    @classmethod
    async def get_instance(cls) -> "WeChatSender":
        """获取单例，线程安全。"""
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ==================== 连接管理 ====================

    def _ensure_connected(self) -> bool:
        """确保微信客户端已连接，断线时先保活进程再重连。"""
        if self._connected and self._wx and self._wx.is_connected:
            return True

        cfg = _get_config()

        # 保活：确保微信进程在运行
        if not _ensure_wechat_process(cfg):
            logger.error("微信进程不可用，跳过发送")
            return False

        WeChatClient = _import_wechat_client()
        if WeChatClient is None:
            logger.error("WeChatClient 不可用，跳过发送")
            return False

        try:
            if self._wx is None:
                self._wx = WeChatClient()

            logger.info("正在连接微信...")
            result = self._wx.connect()
            self._connected = result
            if result:
                logger.info("微信连接成功")
            else:
                logger.error("微信连接失败（进程存在但连接未就绪，可能仍在登录中）")
            return result
        except Exception as e:
            logger.exception(f"微信连接异常: {e}")
            self._connected = False
            return False

    # ==================== 发送 ====================

    async def send_report(self, group_name: str, composed_image: Image.Image) -> bool:
        """
        将合成图片发送到指定微信群，失败时自动重试。

        Args:
            group_name:     目标微信群名称
            composed_image: 合成好的 PIL Image 对象

        Returns:
            bool: 发送是否成功
        """
        cfg = _get_config()
        retry_count = cfg.SEND_RETRY_COUNT
        retry_delay = cfg.SEND_RETRY_DELAY

        async with self._send_lock:
            for attempt in range(retry_count + 1):
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._send_sync, group_name, composed_image
                )
                if result:
                    return True
                if attempt < retry_count:
                    logger.warning(
                        f"发送失败，{retry_delay}s 后重试（第 {attempt + 1}/{retry_count} 次）"
                    )
                    self._connected = False  # 强制下次重连
                    await asyncio.sleep(retry_delay)
            return False

    def _send_sync(self, group_name: str, composed_image: Image.Image) -> bool:
        """同步执行发送（在线程池中运行，避免阻塞事件循环）。"""
        tmp_path = None
        try:
            # 确保连接（含进程保活）
            if not self._ensure_connected():
                return False

            # 写入临时文件
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="baogong_")
            os.close(tmp_fd)

            composed_image.save(tmp_path, format="JPEG", quality=92)
            abs_path = os.path.abspath(tmp_path)

            logger.info(f"准备发送报工图到群「{group_name}」，临时文件：{abs_path}")

            # 调用 wx4py 发送
            success = self._wx.chat_window.send_file_to(
                group_name,
                abs_path,
                target_type="group",
            )

            if success:
                logger.info(f"报工图发送成功 -> 群「{group_name}」")
            else:
                logger.error(f"报工图发送失败 -> 群「{group_name}」")

            return success

        except Exception as e:
            logger.exception(f"发送报工图时发生异常: {e}")
            self._connected = False
            return False

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    logger.debug(f"临时文件已删除: {tmp_path}")
                except Exception as e:
                    logger.warning(f"临时文件删除失败: {tmp_path}, 原因: {e}")


# ==================== 便捷函数 ====================

async def send_report_image(group_name: str, composed_image: Image.Image) -> bool:
    """
    快捷发送函数。

    Args:
        group_name:     目标微信群名称
        composed_image: 合成好的 PIL Image 对象

    Returns:
        bool: 是否发送成功
    """
    sender = await WeChatSender.get_instance()
    return await sender.send_report(group_name, composed_image)
