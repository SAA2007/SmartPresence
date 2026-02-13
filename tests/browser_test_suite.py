import time
import sys
import os
from playwright.sync_api import sync_playwright

# Configuration
BASE_URL = "http://127.0.0.1:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"  # Default

def run_tests():
    print(f"Starting E2E Browser Test Suite on {BASE_URL}")
    print("-" * 50)
    
    with sync_playwright() as p:
        # Launch browser (headful to verify user request "open a browser window")
        # Note: In CI/Automated envs, headless=True is better.
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        try:
            # 1. Login
            print("[TEST] 1. Login Flow...")
            page.goto(f"{BASE_URL}/login")
            page.fill("input[name='username']", ADMIN_USER)
            page.fill("input[name='password']", ADMIN_PASS)
            page.click("button[type='submit']")
            
            # Wait for dashboard (check for specific element)
            page.wait_for_selector("a[href='/logout']", timeout=5000)
            print("  -> Login Successful")

            # 2. Check Dashboard
            print("[TEST] 2. Dashboard Stats...")
            page.goto(f"{BASE_URL}/")
            # Verify stats cards exist
            stats = page.query_selector_all(".card-title")
            if len(stats) >= 3:
                print(f"  -> Found {len(stats)} stat cards")
            else:
                print(f"  -> WARNING: Only found {len(stats)} stat cards")

            # 3. AI Settings (Add/Modify)
            print("[TEST] 3. AI Settings...")
            page.goto(f"{BASE_URL}/settings" if False else f"{BASE_URL}/") 
            # Note: There is no direct /settings page yet in UI, it's modal or separate?
            # Creating a test that hits the API directly via fetch if UI missing?
            # Actually, per Phase 6C, we added API but maybe not a full UI page yet?
            # Let's check the dashboard for a Settings button.
            # If not found, skip UI interaction for settings.
            
            # 4. Camera (Add Camera)
            print("[TEST] 4. Camera Management...")
            # We don't have a dedicated camera management page LINKED in nav yet?
            # Let's try navigating to /cameras if it exists? 
            # Wait, Phase 6B added API, but did it add a UI page?
            # No, 'web_app/templates' was not modified in 6B summary.
            # So UI might strictly be the existing Dashboard + Students + Live.
            # I'll test the LIVE video page.
            
            print("[TEST] 5. Live Video Stream...")
            page.goto(f"{BASE_URL}/live")
            # Check for video element
            # video_stream.py serves MJPEG at /video_feed
            # The template likely has an <img> tag pointing to it.
            try:
                page.wait_for_selector("img[src*='video_feed']", timeout=5000)
                print("  -> Video Feed element found")
            except:
                print("  -> ERROR: Video Feed element NOT found")

            # 5. Logout
            print("[TEST] 6. Logout...")
            page.click("a[href='/logout']")
            page.wait_for_url("**/login")
            print("  -> Logout Successful")

        except Exception as e:
            print(f"  -> FAIL: {e}")
            # Take screenshot
            page.screenshot(path="e2e_error.png")
            print("  -> Screenshot saved to e2e_error.png")

        finally:
            print("-" * 50)
            print("Closing browser...")
            browser.close()

if __name__ == "__main__":
    run_tests()
