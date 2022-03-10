# This file is part of the SLA firmware
# Copyright (C) 2022 Prusa Development a.s. - www.prusa3d.com
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
import cairo

from slafw.hardware.base.exposure_screen import Layer

def draftsman(function):
    @functools.wraps(function)
    def inner(layer: Layer, *args):
        cf = cairo.Format.A8
        surface = cairo.ImageSurface.create_for_data(
                layer.shm_data,
                cf,
                layer.width,
                layer.height,
                cf.stride_for_width(layer.width))
        function(
                cairo.Context(surface),
                *args,
                width = layer.width,
                height = layer.height)
        surface.finish()
    return inner

def _fill_white(ctx: cairo.Context):
    ctx.set_operator(cairo.Operator.OVER)
    ctx.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    ctx.paint()

def _offsets(size: int, width: int, height: int):
    offset_w = (width % size + size) // 2
    offset_h = (height % size + size) // 2
    return offset_w, offset_h

@draftsman
def draw_white(ctx: cairo.Context, **kwargs):
    _fill_white(ctx)

@draftsman
def draw_chess(ctx: cairo.Context, size: int, width: int, height: int):
    _fill_white(ctx)
    ctx.set_operator(cairo.Operator.DEST_OUT)
    offset_w, offset_h = _offsets(size, width, height)
    for y in range(offset_h, height - offset_h, 2 * size):
        ctx.move_to(offset_w, y + size // 2)
        ctx.rel_line_to(width - 2 * offset_w, 0)
        ctx.set_dash((size,), size)
        ctx.set_line_width(size)
    ctx.stroke()
    for y in range(offset_h + size, height - offset_h, 2 * size):
        ctx.move_to(offset_w, y + size // 2)
        ctx.rel_line_to(width - 2 * offset_w, 0)
        ctx.set_dash((size,), 0)
        ctx.set_line_width(size)
    ctx.stroke()

@draftsman
def draw_grid(ctx: cairo.Context, square: int, line: int, width: int, height: int):
    _fill_white(ctx)
    ctx.set_operator(cairo.Operator.DEST_OUT)
    size = square + line
    offset_w, offset_h = _offsets(size, width, height)
    for y in range(offset_h, height - offset_h, size):
        ctx.move_to(offset_w, y + square / 2)
        ctx.rel_line_to(width - 2 * offset_w, 0)
        ctx.set_dash((square, line), 0)
        ctx.set_line_width(square)
    ctx.stroke()

@draftsman
def draw_gradient(ctx: cairo.Context, vertical: bool, width: int, height: int):
    _fill_white(ctx)
    ctx.set_operator(cairo.Operator.DEST_OUT)
    pat = cairo.LinearGradient(0, 0, width * (not vertical), height * vertical)
    pat.add_color_stop_rgba(0.0, 0.0, 0.0, 0.0, 0.0)
    pat.add_color_stop_rgba(1.1, 1.0, 1.0, 1.0, 1.0)
    ctx.set_source(pat)
    ctx.paint()

@draftsman
def inverse(ctx: cairo.Context, **kwargs):
    ctx.set_operator(cairo.Operator.XOR)
    ctx.set_source_rgba(1.0, 1.0, 1.0, 1.0)
    ctx.paint()

@draftsman
def draw_perpartes_mask(ctx: cairo.Context, **kwargs):
    pass
