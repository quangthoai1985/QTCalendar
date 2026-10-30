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
    assert wp.flags & win32.SWP_NOZORDER


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
    assert wp.flags & win32.SWP_NOZORDER


def test_handle_windowposchanging_allow_hide_keeps_hidewindow():
    """Khi chính ứng dụng ẩn widget (allow_hide), không đổi SWP_HIDEWINDOW thành hiện."""
    wp = win32.WINDOWPOS()
    wp.x = 100
    wp.y = 100
    wp.flags = win32.SWP_HIDEWINDOW

    lparam = ctypes.addressof(wp)
    desktop_pin.handle_windowposchanging(lparam, allow_hide=True)

    assert wp.flags & win32.SWP_HIDEWINDOW
    assert not (wp.flags & win32.SWP_SHOWWINDOW)


def test_handle_windowposchanging_normal_click_keeps_no_zorder():
    """Khi click chuột hoặc kéo thả thường (không có SWP_NOSENDCHANGING), giữ nguyên Z-order."""
    wp = win32.WINDOWPOS()
    wp.x = 200
    wp.y = 200
    wp.flags = win32.SWP_SHOWWINDOW

    lparam = ctypes.addressof(wp)
    handled = desktop_pin.handle_windowposchanging(lparam)

    assert handled is True
    assert wp.flags & win32.SWP_NOZORDER


def test_handle_windowposchanging_internal_zpos_allowed():
    """Lệnh SetWindowPos nội bộ của desktop_pin có cờ SWP_NOSENDCHANGING không bị chặn."""
    wp = win32.WINDOWPOS()
    wp.x = 200
    wp.y = 200
    wp.flags = win32.SWP_NOSENDCHANGING

    lparam = ctypes.addressof(wp)
    handled = desktop_pin.handle_windowposchanging(lparam)

    assert handled is False


def test_pin_and_unpin():
    dummy_hwnd = 123456
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch("qtcalendar.platform.win32.get_window_long", return_value=0), \
         patch("qtcalendar.platform.win32.set_window_long", return_value=0), \
         patch("qtcalendar.platform.win32.set_window_pos", return_value=True), \
         patch.object(desktop_pin, "_ensure_sentinel", return_value=9999), \
         patch.object(desktop_pin, "_setup_event_hook", return_value=None), \
         patch.object(desktop_pin, "update_z_order", return_value=None):

        assert desktop_pin.pin(dummy_hwnd) is True
        assert desktop_pin.is_pinned(dummy_hwnd) is True

        assert desktop_pin.unpin(dummy_hwnd) is True
        assert desktop_pin.is_pinned(dummy_hwnd) is False


def test_update_z_order_show_desktop():
    dummy_hwnd = 123456
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=True), \
         patch.object(desktop_pin, "_find_taskbar_window", return_value=5555), \
         patch("qtcalendar.platform.win32.is_window_visible", return_value=True), \
         patch.object(desktop_pin, "_start_restore_poll"), \
         patch("qtcalendar.platform.win32.set_window_pos") as mock_set_pos:

        desktop_pin.update_z_order(dummy_hwnd)
        # Nâng lên TOPMOST và chèn sau taskbar
        assert mock_set_pos.call_count == 2
        calls = mock_set_pos.call_args_list
        assert calls[0][0][1] == win32.HWND_TOPMOST
        assert calls[1][0][1] == 5555


def test_update_z_order_normal():
    dummy_hwnd = 123456
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=False), \
         patch("qtcalendar.platform.win32.set_window_pos") as mock_set_pos:

        desktop_pin.update_z_order(dummy_hwnd)
        # Đưa về HWND_BOTTOM
        assert mock_set_pos.call_count == 1
        assert mock_set_pos.call_args[0][1] == win32.HWND_BOTTOM


# --------------------------------------------------------------------------- #
# Hồi quy v1.1.2: bấm Win + D lần nữa, widget đè lên ứng dụng ~1 giây
# --------------------------------------------------------------------------- #
def test_vao_show_desktop_bat_timer_do_thoat():
    """EVENT_SYSTEM_FOREGROUND đến TRƯỚC khi Explorer hạ lớp Desktop ⇒ phải dò tiếp."""
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=True), \
         patch.object(desktop_pin, "_find_taskbar_window", return_value=0), \
         patch("qtcalendar.platform.win32.set_window_pos"), \
         patch.object(desktop_pin, "_start_restore_poll") as start, \
         patch.object(desktop_pin, "_stop_restore_poll") as stop:

        desktop_pin.update_z_order(123456)

        start.assert_called_once()
        stop.assert_not_called()


def test_ve_binh_thuong_tat_timer_do_thoat():
    with patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=False), \
         patch("qtcalendar.platform.win32.set_window_pos"), \
         patch.object(desktop_pin, "_start_restore_poll") as start, \
         patch.object(desktop_pin, "_stop_restore_poll") as stop:

        desktop_pin.update_z_order(123456)

        stop.assert_called_once()
        start.assert_not_called()


def test_timer_do_thoat_ha_widget_khi_desktop_da_ha():
    with patch.object(desktop_pin, "_pinned_hwnds", {123456}), \
         patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=False), \
         patch.object(desktop_pin, "_stop_restore_poll") as stop, \
         patch("qtcalendar.platform.win32.set_window_pos") as mock_set_pos:

        desktop_pin._on_restore_poll(0, 0, 0, 0)

        assert mock_set_pos.call_args[0][0] == 123456
        assert mock_set_pos.call_args[0][1] == win32.HWND_BOTTOM
        stop.assert_called()


def test_timer_do_thoat_khong_dao_z_order_khi_van_show_desktop():
    """Vẫn đang Show Desktop: không SetWindowPos mỗi nhịp timer (tránh đảo Z-order liên tục)."""
    with patch.object(desktop_pin, "_pinned_hwnds", {123456}), \
         patch("qtcalendar.platform.win32.is_window", return_value=True), \
         patch.object(desktop_pin, "is_show_desktop_active", return_value=True), \
         patch.object(desktop_pin, "_stop_restore_poll") as stop, \
         patch("qtcalendar.platform.win32.set_window_pos") as mock_set_pos:

        desktop_pin._on_restore_poll(0, 0, 0, 0)

        mock_set_pos.assert_not_called()
        stop.assert_not_called()


@pytest.mark.skipif(not desktop_pin.IS_WINDOWS, reason="Timer Win32 chỉ có trên Windows")
def test_timer_do_thoat_chay_trong_vong_lap_qt():
    """Timer Win32 (SetTimer) phải được vòng lặp sự kiện Qt phát tới callback."""
    pytest.importorskip("PySide6")
    import time

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    calls = []
    with patch.object(desktop_pin, "is_show_desktop_active", side_effect=lambda: calls.append(1) or True):
        desktop_pin._start_restore_poll()
        try:
            deadline = time.monotonic() + 0.6
            while time.monotonic() < deadline and len(calls) < 3:
                app.processEvents()
                time.sleep(0.005)
        finally:
            desktop_pin._stop_restore_poll()
    assert len(calls) >= 3
    assert desktop_pin._restore_timer == 0
