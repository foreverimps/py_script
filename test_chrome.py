from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

print("Step 1: Installing ChromeDriver...")
try:
    service = Service(ChromeDriverManager().install())
    print(f"ChromeDriver installed at: {service.path}")
except Exception as e:
    print(f"Error installing ChromeDriver: {e}")
    exit(1)

print("\nStep 2: Creating Chrome options...")
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

print("\nStep 3: Attempting to connect to Chrome...")
try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("SUCCESS: Connected to Chrome!")
    print(f"Current URL: {driver.current_url}")
    driver.quit()
except Exception as e:
    print(f"ERROR: {e}")
    print("\nTrying without debuggerAddress...")

    # Try without connecting to existing Chrome
    chrome_options2 = Options()
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options2)
        print("SUCCESS: Opened new Chrome instance!")
        driver.get("https://www.douyin.com")
        print(f"Opened URL: {driver.current_url}")
        driver.quit()
    except Exception as e2:
        print(f"ERROR: {e2}")
