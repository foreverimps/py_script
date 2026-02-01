# Python 脚本集合 (Python Scripts Collection)

这是一个个人使用的 Python 实用脚本集合。

## 通用前置条件 (Prerequisites)

大多数脚本依赖于 Python 3 环境。部分脚本可能有特定的依赖项（如下所述）。

*   **Python 3**: 请确保已安装。
*   **依赖安装**: 如果脚本有 `requirements.txt`，请运行 `pip3 install -r requirements.txt`。

---

## 脚本列表 (Scripts List)

### 1. 安卓手机截图工具 (`android_screenshot.py`)

**功能描述**:
通过 ADB (Android Debug Bridge) 连接安卓手机，进行屏幕截图并将图片自动保存到电脑本地文件夹，同时清理手机上的临时文件。

**依赖项**:
*   `adb` 命令 (Android Platform Tools) 需要安装并配置在系统 PATH 中。
*   手机需开启“USB 调试”模式。

**包含方法 (Key Functions)**:
*   `take_screenshot(output_dir=".")`:
    *   执行截图逻辑。
    *   参数 `output_dir`: 截图保存的本地目录，默认为当前目录。

**使用方法 (Usage)**:

1.  连接手机并确认 USB 调试已授权。
2.  在终端运行：
    ```bash
    python3 android_screenshot.py
    ```
3.  截图将保存为 `screenshot_YYYYMMDD_HHMMSS.png`。

### 2. 抖音自动打开工具 (`open_douyin.py`)

**功能描述**:
自动打开 Google Chrome 浏览器，将窗口大小调整为 16:9 的比例 (1280x720)，并加载抖音网页版。这有助于在特定尺寸下浏览或展示内容。

**依赖项**:
*   `selenium` 库: 运行 `pip3 install selenium`。
*   **Google Chrome 浏览器**: 必须已安装。
*   **ChromeDriver**: 必须下载与您 Chrome 版本匹配的驱动，并配置到系统 PATH 中。

**包含方法 (Key Functions)**:
*   `open_douyin_landscape()`:
    *   **智能连接**: 自动检测是否已有开启调试端口的 Chrome 实例。
        *   如果有，直接连接该浏览器。
        *   如果没有，启动一个新的 Chrome 实例并开启调试端口。
    *   指定本地 `chrome_user_data` 目录以保存登录状态。
    *   设置窗口大小为 1280x720 (16:9)。
    *   **后台监控**: 持续检查并自动点击“清屏”。
    *   **退出保留**: 停止脚本 (Ctrl+C) 后，**浏览器会保持开启**。再次运行脚本即可重新接管。

**使用方法 (Usage)**:

1.  确保已安装 selenium 和 chromedriver。
2.  在终端运行：
    ```bash
    python3 open_douyin.py
    ```
3.  **首次运行需手动扫码登录**。
4.  脚本运行期间会持续监控“清屏”。
5.  按 `Ctrl+C` 停止脚本（浏览器不会关闭）。

---

*后续添加的脚本将在此处更新...*
