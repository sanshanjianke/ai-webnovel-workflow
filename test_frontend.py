#!/usr/bin/env python3
"""
前端页面自动化测试脚本
使用 PyAutoGUI 截图分析 + 交互测试
"""

import pyautogui
import time
import os
from datetime import datetime
import subprocess

# 截图保存目录
SCREENSHOT_DIR = "/home/ssjk/talk/test_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def take_screenshot(name):
    """截图并保存"""
    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"{SCREENSHOT_DIR}/{name}_{timestamp}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(filename)
    print(f"  ✓ 截图已保存: {filename}")
    return filename

def click(x, y, duration=0.5):
    """点击指定位置"""
    pyautogui.moveTo(x, y, duration=duration)
    pyautogui.click()
    time.sleep(0.5)

def type_text(text):
    """输入文本"""
    pyautogui.typewrite(text, interval=0.01)
    time.sleep(0.3)

def open_browser():
    """打开浏览器访问前端页面"""
    print("\n[1/8] 正在启动浏览器...")
    # 使用 firefox 打开前端页面
    subprocess.Popen([
        "firefox", "--new-window",
        "http://localhost:5173"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)  # 等待浏览器启动
    take_screenshot("01_initial_load")

def test_navigation():
    """测试侧边栏导航"""
    print("\n[2/8] 测试侧边栏导航...")
    time.sleep(2)
    take_screenshot("02_dashboard")

    # 获取屏幕尺寸
    screen_w, screen_h = pyautogui.size()
    print(f"  屏幕尺寸: {screen_w}x{screen_h}")

    # 侧边栏通常在左侧，尝试点击各个导航项
    # 仪表盘 (假设位置)
    nav_items = [
        ("L1种子", 150, 250),
        ("L2会议", 150, 300),
        ("L3叙事", 150, 350),
        ("L4渲染", 150, 400),
        ("世界书", 150, 450),
        ("设置", 150, 500),
    ]

    for name, x, y in nav_items:
        print(f"  点击导航: {name}")
        click(x, y)
        time.sleep(1)
        take_screenshot(f"03_nav_{name}")

    # 返回仪表盘
    click(150, 200)
    time.sleep(1)

def test_l1_page():
    """测试 L1 种子层页面"""
    print("\n[3/8] 测试 L1 种子层...")
    click(150, 250)  # L1种子
    time.sleep(1)
    take_screenshot("04_l1_form")

    # 尝试填写表单（如果有输入框）
    # 假设表单在屏幕中央偏右位置
    try:
        # 向下滚动查看完整表单
        pyautogui.scroll(-3, 960, 600)
        time.sleep(0.5)
        take_screenshot("04_l1_form_scrolled")
    except Exception as e:
        print(f"  滚动失败: {e}")

def test_l2_page():
    """测试 L2 专家会议页面"""
    print("\n[4/8] 测试 L2 专家会议...")
    click(150, 300)  # L2会议
    time.sleep(1)
    take_screenshot("05_l2_meeting")

    # 尝试点击开始会议按钮（如果有）
    screen_w, screen_h = pyautogui.size()
    center_x, center_y = screen_w // 2, screen_h // 2

    # 尝试在中心区域点击
    click(center_x, center_y + 100)
    time.sleep(1)
    take_screenshot("05_l2_clicked")

def test_l3_page():
    """测试 L3 叙事层页面"""
    print("\n[5/8] 测试 L3 叙事层...")
    click(150, 350)  # L3叙事
    time.sleep(1)
    take_screenshot("06_l3_narrative")

    # 测试拖拽标签（如果有）
    screen_w, screen_h = pyautogui.size()
    try:
        # 假设标签在右侧，拖拽到中央区域
        pyautogui.moveTo(screen_w - 200, 400, duration=0.5)
        pyautogui.dragTo(screen_w // 2, 400, duration=0.5)
        time.sleep(0.5)
        take_screenshot("06_l3_drag_test")
    except Exception as e:
        print(f"  拖拽测试失败: {e}")

def test_l4_page():
    """测试 L4 渲染层页面"""
    print("\n[6/8] 测试 L4 渲染层...")
    click(150, 400)  # L4渲染
    time.sleep(1)
    take_screenshot("07_l4_render")

def test_worldbook_page():
    """测试世界书页面"""
    print("\n[7/8] 测试世界书...")
    click(150, 450)  # 世界书
    time.sleep(1)
    take_screenshot("08_worldbook")

    # 尝试滚动查看条目列表
    try:
        pyautogui.scroll(-3, 960, 600)
        time.sleep(0.5)
        take_screenshot("08_worldbook_scrolled")
    except Exception as e:
        print(f"  滚动失败: {e}")

def test_settings_page():
    """测试设置页面"""
    print("\n[8/8] 测试设置页面...")
    click(150, 500)  # 设置
    time.sleep(1)
    take_screenshot("09_settings")

def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("前端页面自动化测试")
    print("=" * 60)

    # 设置 PyAutoGUI 安全模式
    pyautogui.FAILSAFE = True  # 将鼠标移到左上角可中止
    pyautogui.PAUSE = 0.5

    try:
        open_browser()
        test_navigation()
        test_l1_page()
        test_l2_page()
        test_l3_page()
        test_l4_page()
        test_worldbook_page()
        test_settings_page()

        print("\n" + "=" * 60)
        print("测试完成！截图保存在: " + SCREENSHOT_DIR)
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n\n测试出错: {e}")
        take_screenshot("error_state")

if __name__ == "__main__":
    run_tests()
