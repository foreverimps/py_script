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

# Configuration
DEBUG_PORT = 9222
CHROME_USER_DATA_DIR = os.path.join(os.getcwd(), "chrome_user_data")

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
            
            # Check 1: Sidebar elements
            # METHOD CHANGE: Use JS to get full page text. This is more reliable than XPath for "existence" checks.
            # We intentionally do NOT wrap this in a broad try-except that swallows the error.
            # If the window is closed, execute_script will raise WebDriverException, 
            # which will be caught by the OUTER exception handler to trigger window recovery.
            page_text = driver.execute_script("return document.body.innerText;")
            
            if "看相关" in page_text:
                is_cluttered = True
                clutter_reason = "Found '看相关' in page text"
            else:
                # Debug: If not found, what DOES the page contain?
                if iteration % 10 == 0:
                    snippet = page_text[:100].replace('\n', ' ')
                    print(f"[Debug] Page text snippet: {snippet}...")

            # Check 2: Explicit "Clear Screen" button REMOVED as per user request.
            # We now rely SOLELY on "看相关" to detect normal mode.

            if not is_cluttered:
                # If no clutter is visible, we are likely already in Clear Mode.
                if iteration % 5 == 0:
                     print(f"[{time.strftime('%H:%M:%S')}] State: Clear Mode Active ('看相关' hidden). Standing by.")
                time.sleep(1)
                # continue 
                # COMMENTED OUT 'continue' TEMPORARILY: 
                # If detection is failing, this 'continue' prevents the script from working.
                # For now, we will proceed to check the button text as a secondary confirmation.
            
            # If we reach here, either Clutter is detected OR we are fallback checking.
            if iteration % 5 == 0:
                mode_str = "Normal Mode" if is_cluttered else "Potential Clear Mode ('看相关' not found)"
                print(f"[{time.strftime('%H:%M:%S')}] State: {mode_str}. Scanning logic...")
            
            # ACTION: If clutter is detected, press 'J' to toggle Clear Mode
            if is_cluttered:
                print(f"[{time.strftime('%H:%M:%S')}] {clutter_reason}. Sending 'J' key to clear screen...")
                try:
                    # Strategy: Send 'j' key to the body or active element
                    actions = ActionChains(driver)
                    actions.send_keys("j").perform()
                    print("Sent 'J' key.")
                    
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
        # When connecting to existing Chrome via debuggerAddress, we still need chromedriver
        # but webdriver-manager will handle the driver installation automatically
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver 连接成功!", flush=True)
        
        # Ensure window size is correct
        try:
            target_width = 1280
            target_height = 720
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
            print("\nStopping script...")
            stop_event.set()
            # Do NOT call driver.quit() here, so browser stays open
            
    except Exception as e:
        print(f"Error connecting to Chrome: {e}")
        print("Try closing all Chrome instances and running again.")

if __name__ == "__main__":
    open_douyin_landscape()
