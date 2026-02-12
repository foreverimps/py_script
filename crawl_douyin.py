from playwright.sync_api import sync_playwright
import time
import random
import sys
import json
import os
import base64
import requests

def sanitize_filename(name):
    """Remove invalid characters from filename"""
    import re
    # Replace invalid characters with underscore or remove them
    name = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    # Remove leading/trailing dots and spaces
    name = name.strip('. ')
    return name

def extract_drama_name(collection_raw):
    """
    Extract drama name from collection_raw
    Example: "短剧 · 极寒-70℃：变卖百亿家产，打造末日堡垒" -> "极寒-70℃：变卖百亿家产，打造末日堡垒"
    """
    if not collection_raw or collection_raw == "Unknown":
        return "UnknownDrama"

    # Split by middle dot
    if "·" in collection_raw:
        parts = collection_raw.split("·", 1)
        drama_name = parts[1].strip()
    else:
        drama_name = collection_raw.strip()

    return sanitize_filename(drama_name)

def extract_episode_title(title):
    """
    Extract episode title from full title
    Example: "第5集 | 极寒-70℃：全家变卖百亿家产，打造末日堡垒 故事讲述..." -> "第5集"
    """
    if not title:
        return "Unknown Episode"

    # If there's a pipe "|", take the part before it
    if "|" in title:
        episode_title = title.split("|")[0].strip()
    else:
        # Otherwise, take the first 50 characters
        episode_title = title[:50].strip()

    return sanitize_filename(episode_title)

def download_blob_video(page, video_url, output_path, max_retries=2):
    """
    Download video from blob URL using multiple methods
    """
    methods = [
        ("XMLHttpRequest", download_with_xhr),
        ("Video element capture", download_from_video_element)
    ]

    for method_name, method_func in methods:
        for attempt in range(max_retries):
            try:
                if attempt == 0:
                    print(f"  📥 Trying {method_name}...")
                else:
                    print(f"  🔄 Retry {attempt}/{max_retries}...")

                if method_func(page, video_url, output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size > 102400:  # > 100KB (reasonable video size)
                        print(f"  ✅ Downloaded: {os.path.basename(output_path)} ({file_size / 1024 / 1024:.2f} MB)")
                        return True
                    else:
                        print(f"  ⚠️  File too small ({file_size} bytes), trying next method...")
                        if os.path.exists(output_path):
                            os.remove(output_path)
            except Exception as e:
                error_msg = str(e)[:150]
                print(f"  ⚠️  {error_msg}")
                time.sleep(0.5)

    print(f"  ❌ All download methods failed")
    return False

def download_with_xhr(page, video_url, output_path):
    """Download using XMLHttpRequest (more compatible than fetch)"""
    video_data = page.evaluate("""
        async (url) => {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('GET', url, true);
                xhr.responseType = 'blob';
                xhr.onload = function() {
                    if (xhr.status === 200) {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result.split(',')[1]);
                        reader.onerror = reject;
                        reader.readAsDataURL(xhr.response);
                    } else {
                        reject(new Error('XHR failed with status ' + xhr.status));
                    }
                };
                xhr.onerror = () => reject(new Error('XHR network error'));
                xhr.send();
            });
        }
    """, video_url)

    video_bytes = base64.b64decode(video_data)
    with open(output_path, 'wb') as f:
        f.write(video_bytes)
    return True

def download_from_video_element(page, video_url, output_path):
    """
    Try to extract real video URL from network requests or video element
    This method looks for the actual mp4/m3u8 URL instead of blob URL
    """
    # Wait a bit for video to load
    time.sleep(2)

    # Try to find actual video URL from network requests
    real_url = page.evaluate("""
        () => {
            // Method 1: Check if video has a real src (not blob)
            const video = document.querySelector('video');
            if (video && video.src && !video.src.startsWith('blob:')) {
                return video.src;
            }

            // Method 2: Check source elements
            const sources = document.querySelectorAll('video source');
            for (let source of sources) {
                if (source.src && !source.src.startsWith('blob:')) {
                    return source.src;
                }
            }

            // Method 3: Try to find from video element attributes
            if (video) {
                const possibleAttrs = ['data-src', 'data-video-src', 'data-url'];
                for (let attr of possibleAttrs) {
                    const url = video.getAttribute(attr);
                    if (url && url.startsWith('http')) {
                        return url;
                    }
                }
            }

            return null;
        }
    """)

    if real_url and real_url.startswith('http'):
        # Download using requests
        print(f"  🔗 Found real URL: {real_url[:60]}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://www.douyin.com/'
        }

        response = requests.get(real_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True

    raise Exception("Could not find real video URL")

def crawl_douyin(start_url, start_index=1, count=50, output_file="crawled_data.json", download_videos=True, videos_dir="videos", keep_browser_open=False):
    """
    Crawls Douyin videos, extracts metadata, downloads videos, and saves to JSON.
    """
    crawled_data = []

    # Create videos directory
    if download_videos and not os.path.exists(videos_dir):
        os.makedirs(videos_dir)

    # Load existing data if file exists to avoid overwriting
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding='utf-8') as f:
                crawled_data = json.load(f)
        except:
            pass

    # Storage for captured video URLs
    captured_video_urls = []

    # Create user data directory to persist login state
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".browser_data")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        print("📁 Created browser data directory for persistent login")

    with sync_playwright() as p:
        print("Launching browser with persistent session...")

        # Launch browser with persistent context
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--start-maximized"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Intercept network requests to capture real video URLs
        def handle_response(response):
            try:
                url = response.url
                # Look for video file requests (mp4, m3u8, etc.)
                if any(ext in url for ext in ['.mp4', '.m3u8', '/video/', 'tos-cn', 'douyinvod']):
                    if response.status == 200 and 'video' in response.headers.get('content-type', '').lower():
                        if url not in captured_video_urls:
                            captured_video_urls.append(url)
                            print(f"  🎥 Captured video URL: {url[:80]}...")
            except:
                pass

        page.on("response", handle_response)

        print(f"Navigating to start URL: {start_url}")
        # Increase timeout and use domcontentloaded instead of load
        page.goto(start_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)
        
        try:
            close_btn = page.locator(".dy-account-close")
            if close_btn.is_visible():
                close_btn.click()
        except:
            pass

        for i in range(count):
            current_index = start_index + i
            print(f"\n[Episode {current_index}] Processing...")
            
            video_info = {
                "episode_index": current_index,
                "url": None,
                "title": f"Episode_{current_index}", # Default
                "collection_raw": "Unknown"
            }
            
            try:
                page.wait_for_selector('video', timeout=10000)
                time.sleep(2)
                
                # 1. Extract Video Source
                video_element = page.locator("video").first
                video_src = video_element.get_attribute("src")
                if not video_src:
                     src_element = video_element.locator("source").first
                     if src_element.count() > 0:
                         video_src = src_element.get_attribute("src")
                
                if video_src:
                    video_info["url"] = video_src
                    print(f"  URL: {video_src[:40]}...")
                
                # 2. Extract Title (Episode Name)
                # Try h1 first, then fallback
                try:
                    title_el = page.locator("h1").first
                    if title_el.count() > 0:
                        video_info["title"] = title_el.inner_text().strip()
                    else:
                        # Fallback to data-e2e
                        desc_el = page.locator("[data-e2e='video-desc']").first
                        if desc_el.count() > 0:
                             video_info["title"] = desc_el.inner_text().strip()
                except:
                    pass
                print(f"  Title: {video_info['title'][:40]}...")

                # 3. Extract Collection Info (Theater/Drama Name)
                try:
                    # Look for elements containing the middle dot
                    collection_els = page.get_by_text("·").all()
                    for el in collection_els:
                        text = el.inner_text()
                        if "短剧" in text or "剧场" in text or len(text) < 50: 
                            video_info["collection_raw"] = text.strip()
                            break
                    
                    if video_info["collection_raw"] == "Unknown":
                         mix_el = page.get_by_text("短剧").first
                         if mix_el.count() > 0:
                             parent_text = mix_el.locator("..").inner_text()
                             if "·" in parent_text:
                                 video_info["collection_raw"] = parent_text.strip()
                except:
                    pass
                print(f"  Collection: {video_info['collection_raw']}")

                # Download video if enabled
                if video_src and download_videos:
                    # Extract drama name and episode title
                    drama_name = extract_drama_name(video_info["collection_raw"])
                    episode_title = extract_episode_title(video_info["title"])

                    # Create drama folder
                    drama_folder = os.path.join(videos_dir, drama_name)
                    if not os.path.exists(drama_folder):
                        os.makedirs(drama_folder)
                        print(f"  📁 Created folder: {drama_name}/")

                    # Generate filename
                    filename = f"{episode_title}.mp4"
                    output_path = os.path.join(drama_folder, filename)

                    # Check if already downloaded
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 102400:
                        print(f"  ✓ Video already exists: {filename}")
                        video_info["local_path"] = output_path
                        video_info["downloaded"] = True
                    else:
                        print(f"  ⬇️  Downloading video: {filename}")

                        # Method 1: Try captured video URLs first
                        download_success = False
                        if captured_video_urls:
                            real_url = captured_video_urls[-1]  # Get the latest captured URL
                            print(f"  🔗 Using captured URL: {real_url[:60]}...")
                            try:
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                                    'Referer': 'https://www.douyin.com/'
                                }
                                response = requests.get(real_url, headers=headers, stream=True, timeout=30)
                                response.raise_for_status()

                                with open(output_path, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        if chunk:
                                            f.write(chunk)

                                if os.path.getsize(output_path) > 102400:
                                    download_success = True
                                    print(f"  ✅ Downloaded: {filename} ({os.path.getsize(output_path) / 1024 / 1024:.2f} MB)")
                            except Exception as e:
                                print(f"  ⚠️  Direct download failed: {str(e)[:100]}")

                        # Method 2: Fallback to blob download methods
                        if not download_success:
                            if download_blob_video(page, video_src, output_path):
                                download_success = True

                        if download_success:
                            video_info["local_path"] = output_path
                            video_info["downloaded"] = True
                        else:
                            video_info["downloaded"] = False

                        # Clear captured URLs for next video
                        captured_video_urls.clear()

                # Save to list and file
                if video_src:
                    # Remove duplicates by URL
                    crawled_data = [x for x in crawled_data if x.get('url') != video_src]
                    crawled_data.append(video_info)

                    # Atomic write
                    with open(output_file, "w", encoding='utf-8') as f:
                        json.dump(crawled_data, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"  Error extracting info: {e}")

            # Navigation
            if i < count - 1:
                print("  Navigating...")
                try:
                    page.mouse.click(100, 100)
                    if video_element: video_element.click()
                    time.sleep(0.5)
                    page.keyboard.press("ArrowDown")
                except:
                    page.mouse.wheel(0, 1000)

                # Wait for change
                previous_src = video_info["url"]
                for _ in range(15):
                    time.sleep(1)
                    try:
                        new_video = page.locator("video").first
                        new_src = new_video.get_attribute("src")
                        if not new_src:
                            s = new_video.locator("source").first
                            if s.count() > 0: new_src = s.get_attribute("src")
                            
                        if new_src and new_src != previous_src:
                            break
                    except: pass

        # Close browser or keep it open
        if keep_browser_open:
            print("\n⏸️  Browser will remain open. You can:")
            print("   - Continue browsing manually")
            print("   - Close the browser when done")
            print("   - Next run will reuse this login session")
            print("\n   Press Ctrl+C to exit script (browser stays open)...")
            try:
                # Keep script running but allow Ctrl+C to exit
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n✅ Script exited, browser remains open")
        else:
            context.close()

if __name__ == "__main__":
    # Default values
    target_url = "https://www.douyin.com/video/7595199982089571619"
    start_idx = 1
    enable_download = True  # Download videos by default
    keep_open = False  # Keep browser open by default

    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    if len(sys.argv) > 2:
        start_idx = int(sys.argv[2])
    if len(sys.argv) > 3:
        # Check for special flags
        if sys.argv[3] == "no-download":
            enable_download = False
        elif sys.argv[3] == "keep-open":
            keep_open = True
    if len(sys.argv) > 4:
        if sys.argv[4] == "keep-open":
            keep_open = True

    print("=" * 60)
    print("🎬 Douyin Video Crawler with Auto Download")
    print("=" * 60)
    print(f"📍 Start URL: {target_url}")
    print(f"📊 Start Episode: {start_idx}")
    print(f"⬇️  Download Videos: {'Yes' if enable_download else 'No'}")
    print(f"🔓 Persistent Login: Yes (cookies saved in .browser_data/)")
    print(f"⏸️  Keep Browser Open: {'Yes' if keep_open else 'No'}")
    print("=" * 60)
    print()

    if not os.path.exists(".browser_data"):
        print("💡 TIP: This is your first run. The browser will save your login.")
        print("   After logging in once, future runs will auto-login!\n")
    else:
        print("✅ Using saved login session from previous run\n")

    crawl_douyin(
        target_url,
        start_index=start_idx,
        count=50,
        download_videos=enable_download,
        keep_browser_open=keep_open
    )

    if not keep_open:
        print("\n" + "=" * 60)
        print("✅ Crawling completed!")
        print("📁 Videos saved to: ./videos/[剧名]/[集标题].mp4")
        print("📄 Metadata saved to: crawled_data.json")
        print("🔐 Login session saved to: .browser_data/")
        print("\n💡 Next time you run, you'll be auto-logged in!")
        print("=" * 60)