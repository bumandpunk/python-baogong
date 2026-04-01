# -*- coding: utf-8 -*-
"""
报工服务 FastAPI 主入口

提供两条路由：
  POST /report/material   原材料报工
  POST /report/equipment  设备点检报工

两条路由参数完全相同，仅报工类型文字不同。

请求格式（multipart/form-data）：
  reporter:   str         汇报人姓名
  group_name: str         目标微信群名称
  date:       str (可选)  日期，格式 YYYY.MM.DD，默认当天
  images:     List[File]  多张图片文件（支持 jpg/png/webp 等）

响应格式（JSON）：
  {"success": true/false, "message": "..."}
"""
import io
import logging
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image

# 注册 HEIF/HEIC 支持（iPhone 拍照格式），导入失败时静默跳过
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# 确保 baogong_server 包可以被正确导入（既支持 uvicorn 直接启动，也支持 python -m）
_SERVER_ROOT = Path(__file__).parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from baogong_server.image_composer import ReportMeta, compose_report
from baogong_server.wechat_sender import send_report_image

# ==================== 日志 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ==================== FastAPI App ====================
app = FastAPI(
    title="报工自动发送服务",
    description="接收报工图片，合成标准报工图并自动发送到指定微信群",
    version="1.0.0",
)


# ==================== 工具函数 ====================

def _today_str() -> str:
    """返回今天日期字符串，格式 YYYY.MM.DD。"""
    d = date.today()
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


async def _read_images(files: List[UploadFile]) -> List[Image.Image]:
    """读取上传文件列表，转换为 PIL Image 对象列表。"""
    images = []
    for f in files:
        try:
            data = await f.read()
            img = Image.open(io.BytesIO(data))
            images.append(img)
        except Exception as e:
            logger.warning(f"图片 '{f.filename}' 读取失败，已跳过: {e}")
    return images


def _ok(message: str = "发送成功") -> JSONResponse:
    return JSONResponse(content={"success": True, "message": message})


def _fail(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message},
    )


def _image_to_response(img: Image.Image) -> StreamingResponse:
    """将 PIL Image 转为 PNG StreamingResponse，用于本地预览。"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ==================== 核心处理逻辑 ====================

async def _handle_report(
    report_type: str,
    reporter: str,
    group_name: str,
    date_str: Optional[str],
    images: List[UploadFile],
    preview: bool = False,
) -> JSONResponse:
    """
    通用报工处理逻辑（原材料报工 / 设备点检报工 共用）。
    preview=True 时直接返回合成图片，不发送微信（本地测试用）。
    """
    # 参数校验
    reporter = (reporter or "").strip()
    group_name = (group_name or "").strip()
    if not reporter:
        return _fail("reporter（汇报人）不能为空")
    if not preview and not group_name:
        return _fail("group_name（微信群名）不能为空")
    if not images:
        return _fail("至少需要上传一张图片")

    # 日期处理
    if not date_str or not date_str.strip():
        date_str = _today_str()
    else:
        date_str = date_str.strip()

    logger.info(
        f"收到{report_type}请求 | 汇报人: {reporter} | 群: {group_name} "
        f"| 日期: {date_str} | 图片数: {len(images)} | 预览模式: {preview}"
    )

    # 读取图片
    pil_images = await _read_images(images)
    if not pil_images:
        return _fail("所有图片均读取失败，请检查文件格式")

    # 合成报工图
    try:
        meta = ReportMeta(
            report_type=report_type,
            reporter=reporter,
            date_str=date_str,
            images=pil_images,
        )
        composed = compose_report(meta)
        logger.info(f"图片合成完成，尺寸: {composed.size}")
    except Exception as e:
        logger.exception(f"图片合成失败: {e}")
        return _fail(f"图片合成失败: {e}", status_code=500)

    # 预览模式：直接返回图片
    if preview:
        logger.info("预览模式，返回合成图片（不发送微信）")
        return _image_to_response(composed)

    # 发送到微信群
    try:
        success = await send_report_image(group_name, composed)
    except Exception as e:
        logger.exception(f"微信发送异常: {e}")
        return _fail(f"微信发送异常: {e}", status_code=500)

    if success:
        return _ok(f"{report_type}已成功发送到群「{group_name}」")
    else:
        return _fail(f"微信发送失败，请检查微信客户端是否已登录、群名是否正确", status_code=500)


# ==================== 路由 ====================

@app.post(
    "/report/material",
    summary="原材料报工",
    description="上传原材料报工图片，自动合成并发送到指定微信群。`preview=true` 时直接返回合成图片（本地测试用）",
)
async def report_material(
    reporter: str = Form(..., description="汇报人姓名"),
    group_name: str = Form("", description="目标微信群名称（preview=true 时可留空）"),
    date: Optional[str] = Form(None, description="日期，格式 YYYY.MM.DD，默认今天"),
    images: List[UploadFile] = File(..., description="报工图片（可多张）"),
    preview: bool = False,
):
    return await _handle_report(
        report_type="原材料报工",
        reporter=reporter,
        group_name=group_name,
        date_str=date,
        images=images,
        preview=preview,
    )


@app.post(
    "/report/equipment",
    summary="设备点检报工",
    description="上传设备点检报工图片，自动合成并发送到指定微信群。`preview=true` 时直接返回合成图片（本地测试用）",
)
async def report_equipment(
    reporter: str = Form(..., description="汇报人姓名"),
    group_name: str = Form("", description="目标微信群名称（preview=true 时可留空）"),
    date: Optional[str] = Form(None, description="日期，格式 YYYY.MM.DD，默认今天"),
    images: List[UploadFile] = File(..., description="报工图片（可多张）"),
    preview: bool = False,
):
    return await _handle_report(
        report_type="设备点检报工",
        reporter=reporter,
        group_name=group_name,
        date_str=date,
        images=images,
        preview=preview,
    )


# ==================== 健康检查 ====================

@app.get("/health", summary="健康检查")
async def health():
    return {"status": "ok", "service": "报工自动发送服务"}


# ==================== 本地直接运行 ====================

if __name__ == "__main__":
    import uvicorn
    from baogong_server import config as srv_config

    uvicorn.run(
        "baogong_server.main:app",
        host=srv_config.SERVER_HOST,
        port=srv_config.SERVER_PORT,
        reload=False,
        log_level="info",
    )
