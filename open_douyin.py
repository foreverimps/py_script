# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import sys
import os
import threading
import time
import subprocess
import cv2
import numpy as np
from PIL import Image
import io

# Configuration
BROWSER_DATA_DIR = os.path.join(os.getcwd(), ".browser_data")
CLEAR_BUTTON_OFF = "/Users/zhutaoyu/Downloads/clear.png"  # 清屏按钮关闭状态
CLEAR_BUTTON_ON = "/Users/zhutaoyu/Downloads/clear-open.png"  # 清屏按钮打开状态

# 清屏计数器：记录每一集的清屏次数
clear_screen_counter = {}

def find_image_on_screen(page, template_path, threshold=0.8):
    """
    在屏幕截图底部区域中查找模板图片
    返回: True 如果找到, False 如果未找到
    """
    try:
        # 读取模板图片
        template = cv2.imread(template_path)
        if template is None:
            print(f"无法读取模板图片: {template_path}")
            return False

        template_height = template.shape[0]
        template_width = template.shape[1]

        # 截取当前页面
        screenshot = page.screenshot()
        screenshot_img = Image.open(io.BytesIO(screenshot))
        screenshot_cv = cv2.cvtColor(np.array(screenshot_img), cv2.COLOR_RGB2BGR)

        # 截取底部区域，高度至少要大于模板图片高度
        height = screenshot_cv.shape[0]
        crop_height = max(200, template_height + 50)  # 至少200px或模板高度+50px
        screenshot_cv = screenshot_cv[height-crop_height:height, :]

        # 确保截图区域大于模板图片
        if screenshot_cv.shape[0] < template_height or screenshot_cv.shape[1] < template_width:
            print(f"截图区域 ({screenshot_cv.shape[1]}x{screenshot_cv.shape[0]}) 小于模板图片 ({template_width}x{template_height})")
            return False

        # 模板匹配
        result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            return True
        return False
    except Exception as e:
        print(f"图片匹配错误: {e}")
        return False

def stop_screen_recording():
    """按下 Command + Control + Esc 结束录屏"""
    try:
        print(f"[{time.strftime('%H:%M:%S')}] 按下 Command + Control + Esc 结束录屏...")
        # 使用 osascript 模拟按键
        subprocess.run([
            'osascript', '-e',
            'tell application "System Events" to key code 53 using {command down, control down}'
        ], check=True)
        print("录屏结束命令已发送")
        return True
    except Exception as e:
        print(f"结束录屏失败: {e}")
        return False

def monitor_clear_mode(page, stop_event):
    """
    Periodically checks if 'Clear Mode' (清屏) is enabled.
    If not (i.e., '清屏' button is visible), clicks it to enable.
    """
    print("Auto-Clear Mode Monitor started. Press Ctrl+C to stop script (Browser will stay open).")
    iteration = 0
    while not stop_event.is_set():
        iteration += 1
        try:
            # 1. State Detection: Check if we are ALREADY in Clear Mode
            is_cluttered = False
            clutter_reason = ""

            # Check 1: 使用图片匹配检测"清屏"按钮状态
            print(f"[{time.strftime('%H:%M:%S')}] 检测清屏状态...")
            button_on_found = find_image_on_screen(page, CLEAR_BUTTON_ON, threshold=0.95)
            button_off_found = find_image_on_screen(page, CLEAR_BUTTON_OFF, threshold=0.95)

            if button_on_found and not button_off_found:
                # 清屏按钮已打开，已经在清屏模式
                is_cluttered = False
            elif button_off_found and not button_on_found:
                # 清屏按钮关闭，需要按 J 键
                is_cluttered = True
                clutter_reason = "Found '清屏' button (OFF) in screenshot"

                # 尝试提取集数信息
                import re
                page_text = page.evaluate("() => document.body.innerText")
                episode_match = re.search(r'第(\d+)集', page_text)
                if episode_match:
                    episode_num = int(episode_match.group(1))
                    print(f"[{time.strftime('%H:%M:%S')}] 第{episode_num}集 - 需要清屏")

                    # 记录清屏次数
                    if episode_num not in clear_screen_counter:
                        clear_screen_counter[episode_num] = 0
            elif button_on_found and button_off_found:
                # 两个都匹配到了，说明阈值太低，优先认为是打开状态
                is_cluttered = False
            else:
                # 没有找到任何清屏按钮
                pass

            if not is_cluttered:
                # If no clutter is visible, we are likely already in Clear Mode.
                time.sleep(1)
                continue

            # ACTION: If clutter is detected, press 'J' to toggle Clear Mode
            if is_cluttered:
                print(f"[{time.strftime('%H:%M:%S')}] {clutter_reason}. Sending 'J' key to clear screen...")
                try:
                    # Strategy: Send 'j' key to the page
                    page.keyboard.press("j")
                    print("Sent 'J' key.")

                    # 获取当前集数并增加清屏计数
                    import re
                    page_text = page.evaluate("() => document.body.innerText")
                    episode_match = re.search(r'第(\d+)集', page_text)
                    if episode_match:
                        episode_num = int(episode_match.group(1))
                        if episode_num not in clear_screen_counter:
                            clear_screen_counter[episode_num] = 0
                        clear_screen_counter[episode_num] += 1
                        print(f"[{time.strftime('%H:%M:%S')}] 第{episode_num}集 - 第{clear_screen_counter[episode_num]}次清屏")

                        # 检查是否是第二集的第二次清屏
                        if episode_num == 2 and clear_screen_counter[episode_num] == 2:
                            print(f"[{time.strftime('%H:%M:%S')}] 检测到第二集第二次清屏，准备结束录屏...")
                            time.sleep(1)  # 等待清屏完成
                            stop_screen_recording()

                    # Wait for UI to update
                    time.sleep(3)
                except Exception as e:
                    print(f"Failed to send 'J' key: {e}")

        except Exception as e:
            # Handle window closure or context loss
            print(f"Monitor loop error: {e}")
            # Try to check if page is still valid
            try:
                if "douyin.com" not in page.url:
                    print("未找到活动的抖音窗口。等待重试...")
                    time.sleep(2)
            except:
                print("页面已关闭或失效。等待重试...")
                time.sleep(2)

        time.sleep(1)

def open_douyin_landscape():
    # Create user data directory if not exists
    if not os.path.exists(BROWSER_DATA_DIR):
        os.makedirs(BROWSER_DATA_DIR)
        print("📁 Created browser data directory for persistent login")

    with sync_playwright() as p:
        print("Launching browser with persistent session...")

        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            args=["--start-maximized"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1024, "height": 576}
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            # Open Douyin if not already there
            if "douyin.com" not in page.url:
                page.goto("https://www.douyin.com")

            # 3. Start Monitoring
            stop_event = threading.Event()
            monitor_thread = threading.Thread(target=monitor_clear_mode, args=(page, stop_event))
            monitor_thread.daemon = True
            monitor_thread.start()

            # Keep script running until user interrupts
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[退出] 脚本已停止，浏览器保持打开状态")
                stop_event.set()
                monitor_thread.join(timeout=2)
                print("浏览器已保持打开，可以继续使用")
                return

        except KeyboardInterrupt:
            # Handle Ctrl+C at outer level too
            print("\n[退出] 脚本已停止，浏览器保持打开状态")
            return
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    open_douyin_landscape()
