import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"

def run_uat():
    print(f"Starting UAT Edge Case Suite on {BASE_URL}")
    print("-" * 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=500)
        context = browser.new_context()
        page = context.new_page()

        # ---------------------------------------------------------
        # 1. LOGIN EDGE CASES
        # ---------------------------------------------------------
        print("[UAT] 1. Login Edge Cases...")
        
        # 1a. Invalid Password
        print("  -> Testing Invalid Password...")
        page.goto(f"{BASE_URL}/login")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "wrongpass")
        page.click("button[type='submit']")
        try:
            # Look for error toast or alert
            # The app uses showToast() which creates a div.toast
            # OR the page reloads with flash message?
            # Current login.html uses fetch and shows a custom error div or toast.
            # Let's check for text "Invalid credentials"
            page.wait_for_selector("text=Invalid credentials", timeout=3000)
            print("     [PASS] Error message displayed.")
        except:
            print("     [FAIL] Error message NOT found.")

        # 1b. SQL Injection Attempt
        print("  -> Testing SQL Injection (Username field)...")
        page.fill("input[name='username']", "' OR '1'='1")
        page.fill("input[name='password']", "anything")
        page.click("button[type='submit']")
        try:
            # Should FAIL to login
            page.wait_for_selector("text=Invalid credentials", timeout=3000)
            print("     [PASS] SQL Injection blocked (Login failed correctly).")
        except:
            # If we are logged in, we see 'Dashboard' or similar
            if "dashboard" in page.url or page.query_selector("a[href='/logout']"):
                print("     [CRITICAL FAIL] SQL Injection SUCCESSFUL! Logged in.")
            else:
                print("     [PASS?] No login, but unexpected behavior.")

        # ---------------------------------------------------------
        # 2. VALID LOGIN
        # ---------------------------------------------------------
        print("[UAT] 2. Valid Login (Admin)...")
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "admin123")
        page.click("button[type='submit']")
        page.wait_for_url("**/")
        print("     [PASS] Logged in.")

        # ---------------------------------------------------------
        # 3. STUDENT MANAGEMENT EDGE CASES
        # ---------------------------------------------------------
        print("[UAT] 3. Student Input Validation...")
        page.goto(f"{BASE_URL}/students")

        # 3a. Empty Input
        print("  -> Testing Empty Student Name...")
        page.click("button#add-student-btn") # Open Modal
        page.fill("input#studentName", "")
        # Try to click save. The button calls addStudent()
        # Does addStudent check for empty? verify_ai_config said yes?
        # Let's see if we get an alert or toast.
        # We need to handle dialogs if they use alert()
        
        page.on("dialog", lambda dialog: dialog.accept())
        
        page.click("button[onclick='addStudent()']")
        # If valid, it closes modal. If invalid, it stays or shows error.
        # Check if modal is still visible or error toast.
        # We can check if list increased? No name to check.
        # Ideally, we look for "Name is required" toast.
        try:
            page.wait_for_selector("text=Name is required", timeout=2000)
            print("     [PASS] Empty name rejected.")
        except:
            print("     [FAIL] No error for empty name (or different message).")
        
        # Close modal if open (cancel)
        page.keyboard.press("Escape") 
        time.sleep(0.5)

        # 3b. XSS Injection
        print("  -> Testing XSS Injection...")
        xss_payload = "<script>alert('XSS')</script>"
        page.click("button#add-student-btn")
        page.fill("input#studentName", xss_payload)
        page.click("button[onclick='addStudent()']")
        
        # Verify it was added but ESCAPED
        # We look for the text in the table. 
        # CAUTION: If it executes, we get a dialog!
        # We attached a dialog handler to accept it.
        # But we want to ensure it DOES NOT execute.
        
        # Reload page to be sure it persists and renders
        page.reload()
        
        # Check content
        # .student-name class
        content = page.content()
        if "&lt;script&gt;" in content or "&amp;lt;script&amp;gt;" in content:
            print("     [PASS] XSS Payload appears escaped in HTML source.")
        elif "<script>alert('XSS')</script>" in content:
            print("     [CRITICAL FAIL] XSS Payload found RAW in HTML source!")
        else:
            print("     [INFO] Payload not found? execution check via dialog listener...")

        # Cleanup: Delete the XSS student
        # Find row with the payload name and click delete
        try:
            # Playwright verify text
            # If execution happened, the dialog handler would have triggered? 
            # We can't easily detect "did not trigger" without complex event listeners.
            # But checking source for escaped chars is robust.
            pass
        except:
            pass

        print("-" * 50)
        print("UAT Complete.")
        browser.close()

if __name__ == "__main__":
    run_uat()
