#!/usr/bin/env python3
"""
Graider - SharePoint/OneNote File Watcher
==========================================
Automatically downloads new student submissions from SharePoint/OneNote.

Uses Selenium to log in and check for new files.
"""

import os
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


class SharePointWatcher:
    """Watch a SharePoint/OneNote folder for new student submissions."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the watcher.
        
        Args:
            config_path: Path to config file storing credentials and settings
        """
        self.config_path = config_path or os.path.expanduser("~/.graider_config.json")
        self.config = self._load_config()
        self.downloaded_files = set()  # Track already downloaded files
        self.download_history_path = os.path.expanduser("~/.graider_downloads.json")
        self._load_download_history()
        
    def _load_config(self) -> dict:
        """Load configuration from file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self, sharepoint_url: str, email: str, password: str, 
                    download_folder: str, check_interval: int = 300):
        """
        Save watcher configuration.
        
        Args:
            sharepoint_url: URL to the SharePoint/OneNote folder
            email: Microsoft 365 email
            password: Password (will be stored - consider keychain in production)
            download_folder: Local folder to save downloaded files
            check_interval: Seconds between checks (default 5 minutes)
        """
        self.config = {
            "sharepoint_url": sharepoint_url,
            "email": email,
            "password": password,  # TODO: Use keychain for production
            "download_folder": download_folder,
            "check_interval": check_interval
        }
        
        # Create config directory if needed
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Secure the file (owner read/write only)
        os.chmod(self.config_path, 0o600)
        
    def _load_download_history(self):
        """Load list of already downloaded files."""
        if os.path.exists(self.download_history_path):
            with open(self.download_history_path, 'r') as f:
                data = json.load(f)
                self.downloaded_files = set(data.get('files', []))
    
    def _save_download_history(self):
        """Save list of downloaded files."""
        with open(self.download_history_path, 'w') as f:
            json.dump({'files': list(self.downloaded_files)}, f)
    
    def _get_file_hash(self, filename: str, modified: str) -> str:
        """Create unique hash for a file based on name and modified date."""
        return hashlib.md5(f"{filename}_{modified}".encode()).hexdigest()
    
    def _create_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver with persistent profile."""
        options = Options()
        
        # Use persistent profile to save login session
        profile_dir = os.path.expanduser("~/.graider_chrome_profile")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")
        
        if headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Set download directory
        download_folder = self.config.get('download_folder', os.path.expanduser("~/Downloads/Graider"))
        os.makedirs(download_folder, exist_ok=True)
        
        prefs = {
            "download.default_directory": download_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # Appear more like regular browser (helps with session persistence)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        return driver
    
    def login_to_sharepoint(self, driver: webdriver.Chrome) -> bool:
        """
        Log into Microsoft 365 / SharePoint.
        
        Args:
            driver: Selenium WebDriver instance
            
        Returns:
            True if login successful, False otherwise
        """
        email = self.config.get('email')
        password = self.config.get('password')
        url = self.config.get('sharepoint_url')
        
        if not all([email, password, url]):
            print("❌ Missing configuration. Run save_config() first.")
            return False
        
        try:
            print(f"🔐 Opening SharePoint...")
            driver.get(url)
            
            time.sleep(3)
            
            # Check if we're already logged in (session persisted)
            if "sharepoint.com" in driver.current_url and "login" not in driver.current_url.lower():
                # Check if we can see the folder content
                if "personal" in driver.current_url or "Documents" in driver.current_url:
                    print("✅ Already logged in! (session restored)")
                    return True
            
            print("🔑 Need to log in...")
            
            # Wait for and enter email
            wait = WebDriverWait(driver, 30)
            
            # Microsoft login flow - enter email
            try:
                email_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='loginfmt']"))
                )
                email_input.clear()
                email_input.send_keys(email)
                email_input.send_keys(Keys.RETURN)
                
                time.sleep(3)  # Wait for transition
                
                # Enter password
                password_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[name='passwd']"))
                )
                password_input.clear()
                password_input.send_keys(password)
                password_input.send_keys(Keys.RETURN)
            except:
                # Might already be past login screen
                pass
            
            # WAIT FOR 2FA - give user 120 seconds to complete
            print("⏳ Waiting for 2FA... Complete it in the browser window (you have 2 minutes)")
            
            # Wait until we're on SharePoint (2FA complete)
            for i in range(120):  # Wait up to 120 seconds
                time.sleep(1)
                current_url = driver.current_url
                
                # Check for "Stay signed in?" prompt and click YES
                try:
                    yes_button = driver.find_element(By.CSS_SELECTOR, "input[value='Yes'], button#acceptButton, input#idSIButton9")
                    yes_button.click()
                    print("   Clicked 'Stay signed in' - session will persist")
                    time.sleep(2)
                except:
                    pass
                
                if "sharepoint.com" in current_url and "login" not in current_url.lower():
                    print("✅ 2FA complete! Logged in successfully.")
                    time.sleep(3)  # Let page fully load
                    return True
                if i % 10 == 0 and i > 0:
                    print(f"   Still waiting... ({120-i}s remaining)")
            
            print("❌ Timeout waiting for 2FA")
            return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_file_list(self, driver: webdriver.Chrome) -> list:
        """
        Get list of files in the SharePoint folder.
        
        Returns:
            List of dicts with file info: {name, modified, url, hash}
        """
        files = []
        
        try:
            # Wait for file list to load
            time.sleep(5)
            
            # Get page source and parse for filenames
            from selenium.webdriver.common.action_chains import ActionChains
            
            # Find all name cells
            name_cells = driver.find_elements(By.CSS_SELECTOR, '[class*="NameCell"]')
            print(f"📂 Found {len(name_cells)} items in folder")
            
            for cell in name_cells:
                try:
                    # Get the text (filename)
                    filename = cell.text.strip()
                    
                    if not filename:
                        continue
                    
                    # Skip non-assignment files
                    if not any(filename.lower().endswith(ext) for ext in ['.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png', '.pdf']):
                        continue
                    
                    # Create hash based on filename
                    file_hash = self._get_file_hash(filename, "")
                    
                    files.append({
                        'name': filename,
                        'modified': datetime.now().isoformat(),
                        'hash': file_hash,
                        'element': cell
                    })
                    
                except Exception as e:
                    continue
            
            print(f"📄 Found {len(files)} downloadable files")
            
        except Exception as e:
            print(f"❌ Error getting file list: {e}")
        
        return files
    
    def download_file(self, driver: webdriver.Chrome, file_info: dict) -> bool:
        """
        Download a single file from SharePoint.
        
        Args:
            driver: Selenium WebDriver
            file_info: Dict with file information including element reference
            
        Returns:
            True if download started successfully
        """
        try:
            filename = file_info['name']
            print(f"📥 Downloading: {filename}")
            
            from selenium.webdriver.common.action_chains import ActionChains
            
            element = file_info.get('element')
            if element:
                # Click to select the file
                element.click()
                time.sleep(1)
                
                # Try to find and click download button in toolbar
                try:
                    download_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 
                            'button[data-automationid="downloadCommand"], button[aria-label*="Download"], button[name="Download"]'))
                    )
                    download_btn.click()
                    time.sleep(3)
                except:
                    # Try right-click context menu
                    actions = ActionChains(driver)
                    actions.context_click(element).perform()
                    time.sleep(1)
                    
                    download_option = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, 
                            '//button[contains(text(), "Download")] | //span[contains(text(), "Download")]/..'))
                    )
                    download_option.click()
                    time.sleep(3)
                
                self.downloaded_files.add(file_info['hash'])
                self._save_download_history()
                
                print(f"✅ Downloaded: {filename}")
                return True
            
        except Exception as e:
            print(f"❌ Download failed for {filename}: {e}")
        
        return False
    
    def check_for_new_files(self, headless: bool = True) -> list:
        """
        Check SharePoint for new files and download them.
        
        Args:
            headless: Run browser in headless mode (invisible)
            
        Returns:
            List of newly downloaded file paths
        """
        downloaded = []
        driver = None
        
        try:
            driver = self._create_driver(headless=headless)
            
            if not self.login_to_sharepoint(driver):
                return []
            
            files = self.get_file_list(driver)
            
            # Find new files (not already downloaded)
            new_files = [f for f in files if f['hash'] not in self.downloaded_files]
            
            if not new_files:
                print("📭 No new files found")
                return []
            
            print(f"📬 Found {len(new_files)} new file(s)")
            
            for file_info in new_files:
                if self.download_file(driver, file_info):
                    download_path = os.path.join(
                        self.config.get('download_folder', ''),
                        file_info['name']
                    )
                    downloaded.append(download_path)
            
        except Exception as e:
            print(f"❌ Error checking for files: {e}")
            
        finally:
            if driver:
                driver.quit()
        
        return downloaded
    
    def start_watching(self, callback=None, headless: bool = True):
        """
        Start continuous watching for new files.
        
        Args:
            callback: Function to call with list of new files when found
            headless: Run browser in headless mode
        """
        interval = self.config.get('check_interval', 300)
        
        print(f"👁️  Starting file watcher (checking every {interval} seconds)")
        print(f"📁 Download folder: {self.config.get('download_folder')}")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                print(f"🔍 Checking for new files... ({datetime.now().strftime('%H:%M:%S')})")
                new_files = self.check_for_new_files(headless=headless)
                
                if new_files and callback:
                    callback(new_files)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n👋 Watcher stopped")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(60)  # Wait a minute before retrying


# =============================================================================
# STANDALONE USAGE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Graider SharePoint File Watcher")
    parser.add_argument("--setup", action="store_true", help="Configure watcher settings")
    parser.add_argument("--check", action="store_true", help="Check for new files once")
    parser.add_argument("--watch", action="store_true", help="Start continuous watching")
    parser.add_argument("--visible", action="store_true", help="Show browser window (for debugging)")
    
    args = parser.parse_args()
    
    watcher = SharePointWatcher()
    
    if args.setup:
        print("\n📋 Graider SharePoint Watcher Setup\n")
        
        url = input("SharePoint/OneNote folder URL: ").strip()
        email = input("Microsoft 365 email: ").strip()
        password = input("Password: ").strip()
        download_folder = input("Download folder [~/Downloads/Graider]: ").strip()
        
        if not download_folder:
            download_folder = os.path.expanduser("~/Downloads/Graider")
        
        interval = input("Check interval in seconds [300]: ").strip()
        interval = int(interval) if interval else 300
        
        watcher.save_config(url, email, password, download_folder, interval)
        print("\n✅ Configuration saved!")
        
    elif args.check:
        new_files = watcher.check_for_new_files(headless=not args.visible)
        if new_files:
            print(f"\n📥 Downloaded {len(new_files)} file(s):")
            for f in new_files:
                print(f"  - {f}")
        
    elif args.watch:
        def on_new_files(files):
            print(f"\n🎉 New files ready for grading:")
            for f in files:
                print(f"  - {f}")
            print()
        
        watcher.start_watching(callback=on_new_files, headless=not args.visible)
        
    else:
        parser.print_help()
