# -*- coding: utf-8 -*-
"""
Module quản lý và hiển thị đồ họa Quota cho Antigravity Launcher.
Cung cấp bộ tạo Pill Pixbuf bo tròn với màu gradient chuyển sắc theo % Quota.
"""

import math
import cairo
import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

_PIXBUF_CACHE = {}

def draw_rounded_pill(cr, x, y, w, h, r):
    """Vẽ hình viên thuốc bo tròn bằng Cairo Context."""
    r = min(r, w / 2.0, h / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()

def get_quota_pill_pixbuf(val, is_valid):
    """
    Tạo hoặc lấy từ cache đối tượng GdkPixbuf hiển thị thanh Quota pill.
    Hỗ trợ chuyển sắc mượt (gradient) từ Đỏ -> Vàng -> Xanh lá.
    """
    key = (val if is_valid else -1, is_valid)
    if key in _PIXBUF_CACHE:
        return _PIXBUF_CACHE[key]

    w_box = 112
    h_box = 20
    radius = h_box / 2.0

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w_box, h_box)
    cr = cairo.Context(surface)

    # 1. Rãnh nền (Background track) màu xám trung tính bo tròn
    draw_rounded_pill(cr, 1, 1, w_box - 2, h_box - 2, radius - 1)
    cr.set_source_rgba(0.20, 0.22, 0.26, 0.55)
    cr.fill()

    # 2. Thanh Fill Bar với màu chuyển sắc mượt mà (Fading)
    if is_valid and val > 0:
        fill_w = max(h_box - 2, (w_box - 2) * (min(100, val) / 100.0))
        draw_rounded_pill(cr, 1, 1, fill_w, h_box - 2, radius - 1)

        frac = val / 100.0
        if frac >= 0.5:
            # Chuyển sắc từ Vàng (0.95, 0.70, 0.10) sang Xanh Lục Bảo (0.16, 0.78, 0.35)
            t = (frac - 0.5) * 2.0
            cr_r = 0.95 * (1.0 - t) + 0.16 * t
            cr_g = 0.70 * (1.0 - t) + 0.78 * t
            cr_b = 0.10 * (1.0 - t) + 0.35 * t
        else:
            # Chuyển sắc từ Đỏ Báo Động (0.90, 0.22, 0.20) sang Vàng (0.95, 0.70, 0.10)
            t = frac * 2.0
            cr_r = 0.90 * (1.0 - t) + 0.95 * t
            cr_g = 0.22 * (1.0 - t) + 0.70 * t
            cr_b = 0.20 * (1.0 - t) + 0.10 * t

        cr.set_source_rgb(cr_r, cr_g, cr_b)
        cr.fill()

    # 3. Chữ % (bold, trắng tương phản cao, căn giữa chính xác có bóng mờ)
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(10.5)
    txt = f"{val}%" if is_valid else "--"
    ext = cr.text_extents(txt)
    tx = (w_box - ext.width) / 2.0 - ext.x_bearing
    ty = (h_box - ext.height) / 2.0 - ext.y_bearing

    # Bóng mờ tạo độ nổi
    cr.move_to(tx + 0.5, ty + 0.5)
    cr.set_source_rgba(0, 0, 0, 0.75)
    cr.show_text(txt)

    # Chữ chính màu trắng sáng
    cr.move_to(tx, ty)
    cr.set_source_rgb(1.0, 1.0, 1.0)
    cr.show_text(txt)

    # Chuyển đổi cairo BGRA -> RGBA sang GdkPixbuf.Pixbuf
    raw = bytearray(surface.get_data())
    raw[0::4], raw[2::4] = raw[2::4], raw[0::4]

    pb = GdkPixbuf.Pixbuf.new_from_data(
        bytes(raw),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        w_box,
        h_box,
        surface.get_stride()
    )
    _PIXBUF_CACHE[key] = pb
    return pb
