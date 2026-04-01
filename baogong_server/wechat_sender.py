# -*- coding: utf-8 -*-
"""
微信发送封装模块

单例管理 WeChatClient 连接，使用 asyncio.Lock 串行化发送操作（微信 UIAutomation 不线程安全），
合成图片写入临时文件后发送，发送完成立即删除临时文件。
"""
import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

# 将 wx4py 项目加入 sys.path，使 baogong_server 可以在任意工作目录运行
_WX4PY_ROOT = Path(__file__).parent.parent / "wx4py"
if str(_WX4PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_WX4PY_ROOT))


def _import_wechat_client():
    """延迟导入 WeChatClient，避免在非 Windows 环境下启动时报错。"""
    try:
        from src import WeChatClient  # noqa
        return WeChatClient
    except ImportError as e:
        logger.warning(f"WeChatClient 导入失败（可能不在 Windows 环境）: {e}")
        return None


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
        """确保微信客户端已连接，断线时尝试重连。"""
        if self._connected and self._wx and self._wx.is_connected:
            return True

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
                logger.error("微信连接失败")
            return result
        except Exception as e:
            logger.exception(f"微信连接异常: {e}")
            self._connected = False
            return False

    # ==================== 发送 ====================

    async def send_report(self, group_name: str, composed_image: Image.Image) -> bool:
        """
        将合成图片发送到指定微信群。

        Args:
            group_name:     目标微信群名称
            composed_image: 合成好的 PIL Image 对象

        Returns:
            bool: 发送是否成功
        """
        async with self._send_lock:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._send_sync, group_name, composed_image
            )

    def _send_sync(self, group_name: str, composed_image: Image.Image) -> bool:
        """同步执行发送（在线程池中运行，避免阻塞事件循环）。"""
        tmp_path = None
        try:
            # 确保连接
            if not self._ensure_connected():
                return False

            # 写入临时文件
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="baogong_")
            os.close(tmp_fd)  # 关闭文件描述符，让 PIL 重新打开写入

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
            # 连接可能已断开，重置状态
            self._connected = False
            return False

        finally:
            # 无论成功与否，删除临时文件
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
