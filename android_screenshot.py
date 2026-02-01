import os
import subprocess
import datetime
import time

def take_screenshot(output_dir="."):
    """
    Takes a screenshot on a connected Android device via ADB and saves it locally.
    """
    # Check if ADB is available
    try:
        subprocess.run(["adb", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        print("Error: 'adb' command not found. Please ensure Android SDK Platform-Tools are installed and added to your PATH.")
        return

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Generate filename based on timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    local_path = os.path.join(output_dir, filename)
    remote_path = f"/sdcard/{filename}"

    print(f"Taking screenshot: {filename}...")

    try:
        # 1. Capture screenshot to device storage
        subprocess.run(["adb", "shell", "screencap", "-p", remote_path], check=True)

        # 2. Pull the file to local computer
        subprocess.run(["adb", "pull", remote_path, local_path], check=True)

        # 3. Delete the file from device to save space
        subprocess.run(["adb", "shell", "rm", remote_path], check=True)

        print(f"Success! Saved to: {local_path}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to take screenshot. Error: {e}")

if __name__ == "__main__":
    take_screenshot()
