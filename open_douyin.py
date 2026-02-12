# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import sys
import os
import threading
import time
import subprocess
import socket
import cv2
import numpy as np
from PIL import Image
import io

# Configuration
DEBUG_PORT = 9222
CHROME_USER_DATA_DIR = os.path.join(os.getcwd(), "chrome_user_data")
CLEAR_BUTTON_OFF = "/Users/zhutaoyu/Downloads/clear.png"  # 清屏按钮关闭状态
CLEAR_BUTTON_ON = "/Users/zhutaoyu/Downloads/clear-open.png"  # 清屏按钮打开状态

# 清屏计数器：记录每一集的清屏次数
clear_screen_counter = {}

def find_image_on_screen(driver, template_path, threshold=0.8):
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
        screenshot = driver.get_screenshot_as_png()
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

def is_port_open(port):
    """Check if a port is open on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def launch_chrome_detached():
    """Launches Google Chrome in a detached process with remote debugging enabled."""
    print("Launching new Chrome instance...")
    
    # Common paths for Chrome on macOS
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    ]
    
    chrome_bin = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_bin = path
            break
            
    if not chrome_bin:
        print("Error: Could not find Google Chrome binary.")
        sys.exit(1)

    # Arguments for the detached Chrome
    args = [
        chrome_bin,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={CHROME_USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        # "--window-size=1280,720" # Initial size, though script will resize
    ]

    # Launch as a subprocess that persists after script exit
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait briefly for Chrome to start listening on the port
    for _ in range(10):
        if is_port_open(DEBUG_PORT):
            print("Chrome launched and ready.")
            return
        time.sleep(1)
    
    print("Warning: Chrome launched but port check timed out. Attempting to connect anyway...")

def monitor_clear_mode(driver, stop_event):
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
            # In Clear Mode, sidebar elements like "评论" (Comment), "点赞" (Like), "分享" (Share) should be hidden.
            # We look for them to determine if we need to act.
            is_cluttered = False
            clutter_reason = ""

            # Check 1: 使用图片匹配检测"清屏"按钮状态
            # 两张图片很接近，需要提高匹配阈值并优先检测打开状态
            print(f"[{time.strftime('%H:%M:%S')}] 检测清屏状态...")
            button_on_found = find_image_on_screen(driver, CLEAR_BUTTON_ON, threshold=0.95)
            button_off_found = find_image_on_screen(driver, CLEAR_BUTTON_OFF, threshold=0.95)

            if button_on_found and not button_off_found:
                # 清屏按钮已打开，已经在清屏模式
                is_cluttered = False
            elif button_off_found and not button_on_found:
                # 清屏按钮关闭，需要按 J 键
                is_cluttered = True
                clutter_reason = "Found '清屏' button (OFF) in screenshot"

                # 尝试提取集数信息
                import re
                page_text = driver.execute_script("return document.body.innerText;")
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

            # Check 2: Explicit "Clear Screen" button REMOVED as per user request.
            # We now rely SOLELY on image matching to detect clear mode.

            if not is_cluttered:
                # If no clutter is visible, we are likely already in Clear Mode.
                time.sleep(1)
                continue

            # ACTION: If clutter is detected, press 'J' to toggle Clear Mode
            if is_cluttered:
                print(f"[{time.strftime('%H:%M:%S')}] {clutter_reason}. Sending 'J' key to clear screen...")
                try:
                    # Strategy: Send 'j' key to the body or active element
                    actions = ActionChains(driver)
                    actions.send_keys("j").perform()
                    print("Sent 'J' key.")

                    # 获取当前集数并增加清屏计数
                    import re
                    page_text = driver.execute_script("return document.body.innerText;")
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
            else:
                 # If we didn't detect clutter, we assume we are fine.
                 # Just wait.
                 pass

        except WebDriverException:
            # Handle window closure or context loss
            print("当前窗口已丢失或关闭，正在尝试重新寻找抖音窗口...")
            found_douyin = False
            try:
                # Iterate over all open windows to find one with Douyin
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    if "douyin.com" in driver.current_url:
                        print(f"已重新定位到抖音窗口: {driver.title}")
                        found_douyin = True
                        break
            except Exception as e:
                # If checking handles fails, the browser might be closed entirely
                print(f"尝试恢复窗口时出错 (浏览器可能已关闭): {e}")

            if not found_douyin:
                print("未找到活动的抖音窗口。等待重试...")
                time.sleep(2) # Wait a bit longer before retrying

        except WebDriverException:
            # Handle window closure or context loss
            print("当前窗口已丢失或关闭，正在尝试重新寻找抖音窗口...")
            found_douyin = False
            try:
                # Iterate over all open windows to find one with Douyin
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    if "douyin.com" in driver.current_url:
                        print(f"已重新定位到抖音窗口: {driver.title}")
                        found_douyin = True
                        break
            except Exception as e:
                # If checking handles fails, the browser might be closed entirely
                print(f"尝试恢复窗口时出错 (浏览器可能已关闭): {e}")

            if not found_douyin:
                print("未找到活动的抖音窗口。等待重试...")
                time.sleep(2) # Wait a bit longer before retrying
        except Exception as e:
            print(f"Monitor loop error: {e}")
        
        time.sleep(1)

def open_douyin_landscape():
    # 1. Check if Chrome is already running on the debug port
    if not is_port_open(DEBUG_PORT):
        launch_chrome_detached()
    else:
        print(f"Found existing Chrome on port {DEBUG_PORT}. Connecting...", flush=True)

    # 2. Connect Selenium to the existing/new Chrome
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")

    try:
        print("正在创建 WebDriver 实例...", flush=True)
        # Use cached chromedriver directly to avoid slow network checks
        chromedriver_path = os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/144.0.7559.133/chromedriver-mac-x64/chromedriver")
        if os.path.exists(chromedriver_path):
            print(f"使用缓存的 ChromeDriver: {chromedriver_path}", flush=True)
            service = Service(chromedriver_path)
        else:
            print("正在安装/检查 ChromeDriver...", flush=True)
            service = Service(ChromeDriverManager().install())
        print("ChromeDriver 准备完成，正在连接浏览器...", flush=True)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver 连接成功!", flush=True)
        
        # Ensure window size is correct
        try:
            # 原始大小 1280x720，缩小 20% 后为 1024x576
            target_width = 1024
            target_height = 576
            driver.set_window_size(target_width, target_height)
        except:
            # Sometimes setting window size on an attached session might fail or be unnecessary
            pass
        
        # Open Douyin if not already there (optional check)
        if "douyin.com" not in driver.current_url:
             driver.get("https://www.douyin.com")
        
        # 3. Start Monitoring
        stop_event = threading.Event()
        monitor_thread = threading.Thread(target=monitor_clear_mode, args=(driver, stop_event))
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
            # Detach driver from browser by clearing the command executor
            driver.command_executor._conn = None
            del driver
            print("浏览器已保持打开，可以继续使用")
            return

    except KeyboardInterrupt:
        # Handle Ctrl+C at outer level too
        print("\n[退出] 脚本已停止，浏览器保持打开状态")
        return
    except Exception as e:
        print(f"Error connecting to Chrome: {e}")
        print("Try closing all Chrome instances and running again.")
        sys.exit(1)

if __name__ == "__main__":
    open_douyin_landscape()
