# -*- coding: utf-8 -*-
"""Unit tests cho module desktop_pin (cơ chế Rainmeter Top-Level Pin)."""

import ctypes
from ctypes import wintypes
from unittest.mock import MagicMock, patch

import pytest

from qtcalendar.platform import desktop_pin, win32


def test_handle_windowposchanging_win_d_offscreen():
    wp = win32.WINDOWPOS()
    wp.x = -32000
    wp.y = -32000
    wp.flags = 0

    lparam = ctypes.addressof(wp)
    handled = desktop_pin.handle_windowposchanging(lparam)

    assert handled is True
    assert wp.flags & win32.SWP_NOMOVE
    assert wp.flags & win32.SWP_NOSIZE
    assert wp.hwndInsertAfter == win32.HWND_BOTTOM


def test_handle_windowposchanging_win_d_hidewindow():
    wp = win32.WINDOWPOS()
    wp.x = 100
    wp.y = 100
    wp.flags = win32.SWP_HIDEWINDOW

    lparam = ctypes.addressof(wp)
    handled = desktop_pin.handle_windowposchanging(lparam)

    assert handled is True
    assert not (wp.flags & win32.SWP_HIDEWINDOW)
    assert wp.flags & win32.SWP_SHOWWINDOW
    assert wp.hwndInsertAfter == win32.HWND_BOTTOM


def test_handle_windowposchanging_normal_move():
    wp = win32.WINDOWPOS()
    wp.x = 200
    wp.y = 200
    wp.flags = win32.SWP_SHOWWINDOW

    lparam = ctypes.addressof(wp)
    handled = desktop_pin.handle_windowposchanging(lparam)

    assert handled is False
    assert wp.hwndInsertAfter == win32.HWND_BOTTOM


def test_pin_and_unpin():
    dummy_hwnd = 123456
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch("qtcalendar.platform.win32.get_window_long", return_value=0), \
         patch("qtcalendar.platform.win32.set_window_long", return_value=0), \
         patch("qtcalendar.platform.win32.set_window_pos", return_value=True):

        assert desktop_pin.pin(dummy_hwnd) is True
        assert desktop_pin.is_pinned(dummy_hwnd) is True

        assert desktop_pin.unpin(dummy_hwnd) is True
        assert desktop_pin.is_pinned(dummy_hwnd) is False
