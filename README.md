# Python 脚本集合 (Python Scripts Collection)

这是一个个人使用的 Python 实用脚本集合。

## 通用前置条件 (Prerequisites)

大多数脚本依赖于 Python 3 环境。部分脚本可能有特定的依赖项（如下所述）。

*   **Python 3**: 请确保已安装。
*   **依赖安装**: 如果脚本有 `requirements.txt`，请运行 `pip install -r requirements.txt`。

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

---

*后续添加的脚本将在此处更新...*
