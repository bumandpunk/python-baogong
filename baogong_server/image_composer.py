# -*- coding: utf-8 -*-
"""
报工图片合成模块

将多张图片拼接成标准化报工图，布局如下：
  ┌──────────────────────────────┐
  │       标题区（报 工）         │
  ├──────────────────────────────┤
  │ 汇报人：xxx    日期：xxxx    │
  ├──────────────────────────────┤
  │  图1  │  图2  │  图3         │
  │  图4  │  图5  │  图6         │
  │  ...                         │
  ├──────────────────────────────┤
  │   捷租先登出品                │
  │   本次报工由门神域系统自动上报 │
  └──────────────────────────────┘
"""
import io
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from . import config


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """加载字体，找不到系统字体时回退到 Pillow 内置字体。"""
    font_path = config.FONT_PATH
    if font_path:
        try:
            # msyh.ttc / simhei.ttf 等 TrueType 字体
            # index=1 通常是 Bold，index=0 是 Regular（msyh.ttc）
            font_index = 1 if bold and font_path.endswith(".ttc") else 0
            return ImageFont.truetype(font_path, size=size, index=font_index)
        except Exception:
            pass
    # 回退到 Pillow 内置字体（不支持中文，仅作保底）
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _crop_to_ratio(img: Image.Image, w: int, h: int) -> Image.Image:
    """等比居中裁剪图片到指定宽高比（不拉伸）。"""
    src_w, src_h = img.size
    target_ratio = w / h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # 原图更宽，裁左右
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    elif src_ratio < target_ratio:
        # 原图更高，裁上下
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    return img.resize((w, h), Image.LANCZOS)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """兼容新旧版本 Pillow 获取文字尺寸。"""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(text, font=font)


@dataclass
class ReportMeta:
    """报工元信息"""
    report_type: str              # "原材料报工" 或 "设备点检报工"
    reporter: str                 # 汇报人姓名
    date_str: str                 # "2026.04.01"
    images: List[Image.Image] = field(default_factory=list)


class ImageComposer:
    """报工图片合成器"""

    # ==================== 对外接口 ====================

    def compose(self, meta: ReportMeta) -> Image.Image:
        """
        合成完整报工图。

        Args:
            meta: 报工元信息（类型、汇报人、日期、图片列表）

        Returns:
            PIL Image 对象（RGB模式）
        """
        W = config.CANVAS_WIDTH

        # 预先计算各区块尺寸
        title_h = config.TITLE_HEIGHT
        info_h = config.INFO_BAR_HEIGHT
        grid_h = self._calc_grid_height(len(meta.images), W)
        footer_h = self._calc_footer_height()

        total_h = title_h + info_h + grid_h + footer_h

        canvas = Image.new("RGB", (W, total_h), config.CANVAS_BG_COLOR)

        y = 0
        y = self._draw_title(canvas, y, W, title_h)
        y = self._draw_info_bar(canvas, y, W, info_h, meta.reporter, meta.date_str)
        y = self._draw_grid(canvas, y, W, meta.images)
        self._draw_footer(canvas, y, W, footer_h)

        return canvas

    # ==================== 区块绘制 ====================

    def _draw_title(self, canvas: Image.Image, y: int, W: int, H: int) -> int:
        """绘制标题区（双层红色边框 + "报 工"大字 + 左上角 logo）。"""
        draw = ImageDraw.Draw(canvas)

        # 外边框
        bw = config.TITLE_BORDER_WIDTH
        gap = config.TITLE_INNER_BORDER_GAP
        color = config.TITLE_BORDER_COLOR

        # 外框矩形
        outer = [bw, y + bw, W - bw, y + H - bw]
        draw.rectangle(outer, outline=color, width=bw)

        # 内框矩形（与外框有一定间距，形成双框效果）
        inner_margin = bw + gap
        inner = [inner_margin, y + inner_margin, W - inner_margin, y + H - inner_margin]
        draw.rectangle(inner, outline=color, width=bw)

        # 标题文字
        font = _load_font(config.TITLE_FONT_SIZE, bold=True)
        text = config.TITLE_TEXT
        tw, th = _text_size(draw, text, font)
        tx = (W - tw) // 2
        ty = y + (H - th) // 2 - 4  # 轻微上移视觉居中
        draw.text((tx, ty), text, font=font, fill=config.TITLE_COLOR)

        # 左上角 logo
        import os as _os
        logo_path = config.LOGO_PATH
        if logo_path and _os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                target_h = config.LOGO_SIZE
                ratio = target_h / logo.height
                target_w = int(logo.width * ratio)
                logo = logo.resize((target_w, target_h), Image.LANCZOS)
                margin = config.LOGO_MARGIN
                lx = inner_margin + margin
                ly = y + inner_margin + margin
                # 用 alpha 通道合成，支持透明背景
                canvas.paste(logo, (lx, ly), mask=logo.split()[3])
            except Exception:
                pass

        return y + H

    def _draw_info_bar(
        self, canvas: Image.Image, y: int, W: int, H: int, reporter: str, date_str: str
    ) -> int:
        """绘制信息栏（汇报人 + 日期）。"""
        draw = ImageDraw.Draw(canvas)

        # 背景与边框
        draw.rectangle([0, y, W, y + H], fill=config.INFO_BG_COLOR)

        # 底部分隔线（红色）
        bw = config.INFO_BORDER_WIDTH
        draw.line([(0, y + H - bw), (W, y + H - bw)], fill=config.INFO_BORDER_COLOR, width=bw)

        # 文字
        font = _load_font(config.INFO_FONT_SIZE)
        text_color = config.INFO_TEXT_COLOR
        pad = config.PADDING

        left_text = f"汇报人：{reporter}"
        right_text = f"日期：{date_str}"

        # 垂直居中
        _, th = _text_size(draw, left_text, font)
        ty = y + (H - th) // 2

        draw.text((pad, ty), left_text, font=font, fill=text_color)

        rw, _ = _text_size(draw, right_text, font)
        draw.text((W - pad - rw, ty), right_text, font=font, fill=text_color)

        return y + H

    def _calc_grid_height(self, n_images: int, W: int) -> int:
        """计算图片网格区总高度。"""
        if n_images == 0:
            return 0
        cols = config.GRID_COLS
        gap = config.GRID_GAP
        rows = math.ceil(n_images / cols)

        cell_w = (W - gap * (cols + 1)) // cols
        aspect_w, aspect_h = config.GRID_ASPECT
        cell_h = int(cell_w * aspect_h / aspect_w)

        return rows * cell_h + (rows + 1) * gap

    def _draw_grid(self, canvas: Image.Image, y: int, W: int, images: List[Image.Image]) -> int:
        """绘制图片网格区。"""
        if not images:
            return y

        cols = config.GRID_COLS
        gap = config.GRID_GAP
        aspect_w, aspect_h = config.GRID_ASPECT

        cell_w = (W - gap * (cols + 1)) // cols
        cell_h = int(cell_w * aspect_h / aspect_w)

        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols

            x = gap + col * (cell_w + gap)
            cell_y = y + gap + row * (cell_h + gap)

            # 裁剪缩放
            cell_img = _crop_to_ratio(img.convert("RGB"), cell_w, cell_h)
            canvas.paste(cell_img, (x, cell_y))

        rows = math.ceil(len(images) / cols)
        grid_h = rows * cell_h + (rows + 1) * gap
        return y + grid_h

    def _calc_footer_height(self) -> int:
        """计算底部品牌区高度。"""
        # 两行文字 + 行间距 + 上下内边距
        line_h = config.FOOTER_FONT_SIZE + 8  # 行高 ≈ 字号 + 行间距
        return (
            config.FOOTER_PADDING_V * 2
            + line_h * 2
            + config.FOOTER_LINE_GAP
        )

    def _draw_footer(self, canvas: Image.Image, y: int, W: int, H: int) -> None:
        """绘制底部品牌区。"""
        draw = ImageDraw.Draw(canvas)

        # 背景
        draw.rectangle([0, y, W, y + H], fill=config.FOOTER_BG_COLOR)

        font = _load_font(config.FOOTER_FONT_SIZE)
        color = config.FOOTER_TEXT_COLOR
        pad_v = config.FOOTER_PADDING_V
        line_gap = config.FOOTER_LINE_GAP

        lines = [config.FOOTER_LINE1, config.FOOTER_LINE2]
        line_h = config.FOOTER_FONT_SIZE + 8

        total_text_h = len(lines) * line_h + (len(lines) - 1) * line_gap
        text_start_y = y + (H - total_text_h) // 2

        for i, line in enumerate(lines):
            lw, lh = _text_size(draw, line, font)
            lx = (W - lw) // 2
            ly = text_start_y + i * (line_h + line_gap)
            draw.text((lx, ly), line, font=font, fill=color)


# 模块级便捷函数
_composer = ImageComposer()


def compose_report(meta: ReportMeta) -> Image.Image:
    """快捷合成接口，复用全局 ImageComposer 实例。"""
    return _composer.compose(meta)
