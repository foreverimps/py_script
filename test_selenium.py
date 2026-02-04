#!/usr/bin/env python3
import sys
print("脚本开始运行...", flush=True)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
print("Selenium导入成功", flush=True)

chrome_options = Options()
chrome_options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')
print("Chrome选项配置完成", flush=True)

try:
    print("正在连接Chrome...", flush=True)
    driver = webdriver.Chrome(options=chrome_options)
    print(f"连接成功! 当前URL: {driver.current_url}", flush=True)

    if "douyin.com" not in driver.current_url:
        print("正在打开抖音...", flush=True)
        driver.get("https://www.douyin.com")
        print("抖音已打开", flush=True)
    else:
        print("抖音已经在运行", flush=True)

    print("脚本运行成功!", flush=True)

except Exception as e:
    print(f"错误: {e}", flush=True)
    sys.exit(1)
