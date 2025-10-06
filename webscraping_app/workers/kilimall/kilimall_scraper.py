#!/usr/bin/env python3
"""
Kilimall Web Scraper - SEQUENTIAL VERSION
Fixed to prevent hanging and resource issues.
"""

import json
import csv
import time
import random
import re
import argparse
import logging
import os
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Product:
    """Data class to represent a product"""
    name: str
    price: str
    original_price: str
    discount: str
    rating: str
    reviews_count: str
    image_url: str
    product_url: str
    brand: str
    category: str
    shipping_info: str
    badges: List[str]

class KilimallScraper:
    def __init__(self, headless: bool = True, delay_range: tuple = (2, 4)):
        self.base_url = "https://www.kilimall.co.ke"
        self.delay_range = delay_range
        self.driver = None
        self.wait = None
        self.headless = headless
        
        self.selectors = {
            'product_containers': '.listing-item .product-item',
            'product_title': '.product-title',
            'product_price': '.product-price',
            'product_image': '.product-image img',
            'product_link': 'a[href*="/listing/"]',
            'rating_container': '.rate .van-rate',
            'reviews_count': '.reviews',
            'shipping_badge': '.logistics-tag .tag-name',
            'product_list': '.listings'
        }
        
        self.known_brands = [
            'VITRON', 'SAMSUNG', 'XIAOMI', 'INFINIX', 'TECNO', 'ITEL', 'OPPO', 'REALME',
            'TAGWOOD', 'HISENSE', 'TCL', 'SONAR', 'AILYONS', 'AMTEC', 'GENERIC',
            'NOKIA', 'HUAWEI', 'APPLE', 'ONEPLUS', 'POCO', 'BLACKVIEW', 'RAMTONS'
        ]

    def setup_driver(self):
        """Initialize Chrome driver with appropriate options and timeout."""
        import signal
        from contextlib import contextmanager

        @contextmanager
        def timeout_context(seconds):
            """Context manager for timeout"""
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Chrome driver initialization timed out after {seconds} seconds")

            # Set the signal handler (Unix/Linux only, Windows needs different approach)
            try:
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
                try:
                    yield
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            except AttributeError:
                # Windows doesn't have SIGALRM, so just proceed without timeout
                yield

        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless=new')

            # Add stability options
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')

            # Additional options to prevent hanging
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-breakpad')
            chrome_options.add_argument('--disable-client-side-phishing-detection')
            chrome_options.add_argument('--disable-component-update')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-hang-monitor')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-prompt-on-repost')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--metrics-recording-only')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--safebrowsing-disable-auto-update')
            chrome_options.add_argument('--enable-automation')
            chrome_options.add_argument('--password-store=basic')
            chrome_options.add_argument('--use-mock-keychain')

            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option('prefs', {
                'profile.default_content_setting_values': {
                    'notifications': 2,
                    'media_stream': 2,
                    'media_stream_mic': 2,
                    'media_stream_camera': 2
                }
            })

            chrome_options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )

            logger.info("Initializing Chrome driver...")

            # Try to initialize with a reasonable timeout
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                logger.info("Chrome driver created successfully")
            except Exception as e:
                logger.error(f"Failed to create Chrome driver: {e}")
                # Try to kill any zombie Chrome processes
                try:
                    import subprocess
                    if os.name == 'nt':  # Windows
                        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'],
                                     capture_output=True, timeout=5)
                        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'],
                                     capture_output=True, timeout=5)
                    logger.info("Cleaned up zombie Chrome processes, retrying...")
                    time.sleep(2)
                    self.driver = webdriver.Chrome(options=chrome_options)
                except Exception as retry_error:
                    logger.error(f"Retry also failed: {retry_error}")
                    raise

            # Configure driver after creation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Set timeouts to prevent hanging
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 15)

            logger.info("Chrome driver initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            # Make sure to clean up if initialization failed
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            raise

    def wait_for_page_load(self):
        """Wait for Vue.js content to load by checking for the product list."""
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.selectors['product_list'])))
            time.sleep(2)  # Extra wait for dynamic content to settle
            logger.info("Page loaded successfully")
        except TimeoutException:
            logger.warning("Timeout waiting for page to load completely.")

    def scroll_to_load_content(self):
        """Scroll down the page to trigger lazy-loading of all products."""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 5  # Limit scrolling to prevent infinite loops
            
            while scroll_attempts < max_scrolls:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    break
                    
                last_height = new_height
                scroll_attempts += 1
                
            logger.info(f"Completed scrolling after {scroll_attempts} attempts")
            
        except Exception as e:
            logger.warning(f"Error during scrolling: {e}")

    def extract_brand_from_title(self, title):
        """Extract brand from product title using a predefined list."""
        if not title: 
            return "N/A"
            
        title_upper = title.upper()
        for brand in self.known_brands:
            if brand in title_upper:
                return brand
                
        first_word = title.split()[0].upper() if title.split() else "N/A"
        return first_word if len(first_word) > 1 else "N/A"

    def extract_product_info(self, container):
        """Extract all product information from a single product container element."""
        try:
            # Product name
            try:
                name_element = container.find_element(By.CSS_SELECTOR, self.selectors['product_title'])
                name = name_element.text.strip()
            except NoSuchElementException:
                name = "N/A"

            # Product URL
            try:
                link_element = container.find_element(By.CSS_SELECTOR, self.selectors['product_link'])
                product_url = urljoin(self.base_url, link_element.get_attribute('href'))
            except NoSuchElementException:
                product_url = "N/A"

            # Price - current selling price
            price = "N/A"
            try:
                price_element = container.find_element(By.CSS_SELECTOR, self.selectors['product_price'])
                price = price_element.text.strip()
            except NoSuchElementException:
                pass

            # Original price and discount
            original_price = "N/A"
            discount = "N/A"
            try:
                # Look for strikethrough or old price
                old_price_elem = container.find_element(By.CSS_SELECTOR, '.old-price, .original-price, [class*="old"], [class*="original"]')
                original_price = old_price_elem.text.strip()
            except NoSuchElementException:
                pass

            try:
                # Look for discount badge or percentage
                discount_elem = container.find_element(By.CSS_SELECTOR, '.discount, .discount-tag, [class*="discount"], .percentage-off')
                discount_text = discount_elem.text.strip()
                if discount_text:
                    discount = discount_text
            except NoSuchElementException:
                pass
            
            # Image URL - improved extraction
            image_url = "N/A"
            try:
                img_element = container.find_element(By.CSS_SELECTOR, self.selectors['product_image'])

                # Try multiple attributes in priority order
                for attr in ['src', 'data-src', 'data-lazy-src']:
                    url = img_element.get_attribute(attr)
                    if url and not url.startswith('data:'):
                        image_url = url
                        break

                # If still a data URL or empty, try to get from lazy attribute
                if image_url == "N/A" or (image_url and image_url.startswith('data:')):
                    lazy_attr = img_element.get_attribute('lazy')
                    if lazy_attr:
                        # Some images use lazy="loading" or lazy="loaded"
                        data_src = img_element.get_attribute('data-src')
                        if data_src and not data_src.startswith('data:'):
                            image_url = data_src

            except NoSuchElementException:
                pass

            # Rating and Reviews
            rating, reviews_count = "N/A", "N/A"
            try:
                rating_container = container.find_element(By.CSS_SELECTOR, self.selectors['rating_container'])
                filled_stars = len(rating_container.find_elements(By.CSS_SELECTOR, '.van-rate__icon--full'))
                total_stars = len(rating_container.find_elements(By.CSS_SELECTOR, '.van-rate__item'))
                if total_stars > 0: 
                    rating = f"{filled_stars}/{total_stars}"
                
                reviews_element = container.find_element(By.CSS_SELECTOR, self.selectors['reviews_count'])
                reviews_match = re.search(r'\((\d+)\)', reviews_element.text.strip())
                if reviews_match: 
                    reviews_count = f"{reviews_match.group(1)} reviews"
            except NoSuchElementException:
                pass

            # Brand
            brand = self.extract_brand_from_title(name)
            
            # Shipping and Badges
            shipping_info = "N/A"
            try:
                shipping_element = container.find_element(By.CSS_SELECTOR, self.selectors['shipping_badge'])
                shipping_info = shipping_element.text.strip()
            except NoSuchElementException: 
                pass
            
            badges = []
            try:
                badge_elements = container.find_elements(By.CSS_SELECTOR, '.mark-box > div')
                badges = [badge.text.strip() for badge in badge_elements if badge.text.strip()]
            except NoSuchElementException: 
                pass

            return Product(
                name=name,
                price=price,
                original_price=original_price,
                discount=discount,
                rating=rating,
                reviews_count=reviews_count,
                image_url=image_url,
                product_url=product_url,
                brand=brand,
                category="Electronics",
                shipping_info=shipping_info,
                badges=badges
            )
            
        except Exception as e:
            logger.error(f"Error extracting product info: {e}")
            return None

    def scrape_category(self, category_url: str, max_pages: int = 5, progress_callback=None) -> List[Product]:
        """Scrape products from a category URL."""
        logger.info(f"Starting category scrape from '{category_url}' across {max_pages} pages.")
        all_products = []

        try:
            for page in range(1, max_pages + 1):
                try:
                    # Update progress
                    if progress_callback:
                        progress = (page - 1) / max_pages * 90
                        progress_callback(f"Scraping page {page}/{max_pages}...", progress)

                    # Modify URL to include page number
                    # Remove existing page parameter if present
                    import re
                    base_url = re.sub(r'[&?]page=\d+', '', category_url)

                    # Add page parameter
                    if '?' in base_url:
                        page_url = f"{base_url}&page={page}"
                    else:
                        page_url = f"{base_url}?page={page}"

                    logger.info(f"Navigating to category page {page}: {page_url}")

                    self.driver.get(page_url)
                    self.wait_for_page_load()
                    self.scroll_to_load_content()

                    # Find product containers
                    product_containers = self.driver.find_elements(By.CSS_SELECTOR, self.selectors['product_containers'])
                    logger.info(f"Found {len(product_containers)} product containers on page {page}")

                    page_products = []
                    for container in product_containers:
                        product = self.extract_product_info(container)
                        if product:
                            page_products.append(product)

                    all_products.extend(page_products)
                    logger.info(f"Extracted {len(page_products)} products from page {page}")

                    # Delay between pages
                    if page < max_pages:
                        delay = random.uniform(*self.delay_range)
                        logger.info(f"Waiting {delay:.1f} seconds before next page...")
                        time.sleep(delay)

                except TimeoutException:
                    logger.warning(f"Timeout on page {page}, skipping...")
                    continue
                except Exception as e:
                    logger.error(f"Error on page {page}: {e}")
                    continue

            # Final progress update
            if progress_callback:
                progress_callback(f"Scraping completed! Found {len(all_products)} products", 100)

            logger.info(f"Category scrape complete. Total products found: {len(all_products)}")
            return all_products

        except Exception as e:
            logger.error(f"Critical error during category scrape: {e}")
            return all_products

    def search_products(self, query: str, max_pages: int = 5, progress_callback=None) -> List[Product]:
        """Search for products sequentially (no multiprocessing)."""
        logger.info(f"Starting sequential search for '{query}' across {max_pages} pages.")
        all_products = []

        try:
            for page in range(1, max_pages + 1):
                try:
                    # Update progress
                    if progress_callback:
                        progress = (page - 1) / max_pages * 90  # Reserve 10% for final processing
                        progress_callback(f"Scraping page {page}/{max_pages}...", progress)

                    search_url = f"{self.base_url}/search?q={query}&page={page}"
                    logger.info(f"Navigating to page {page}: {search_url}")

                    self.driver.get(search_url)
                    self.wait_for_page_load()
                    self.scroll_to_load_content()

                    # Find product containers
                    product_containers = self.driver.find_elements(By.CSS_SELECTOR, self.selectors['product_containers'])
                    logger.info(f"Found {len(product_containers)} product containers on page {page}")

                    page_products = []
                    for container in product_containers:
                        product = self.extract_product_info(container)
                        if product:
                            page_products.append(product)
                    
                    all_products.extend(page_products)
                    logger.info(f"Extracted {len(page_products)} products from page {page}")
                    
                    # Delay between pages to be respectful
                    if page < max_pages:
                        delay = random.uniform(*self.delay_range)
                        logger.info(f"Waiting {delay:.1f} seconds before next page...")
                        time.sleep(delay)
                        
                except TimeoutException:
                    logger.warning(f"Timeout on page {page}, skipping...")
                    continue
                except Exception as e:
                    logger.error(f"Error on page {page}: {e}")
                    continue
            
            # Final progress update
            if progress_callback:
                progress_callback(f"Scraping completed! Found {len(all_products)} products", 100)
            
            logger.info(f"Sequential search complete. Total products found: {len(all_products)}")
            return all_products
            
        except Exception as e:
            logger.error(f"Critical error during search: {e}")
            return all_products

    def close(self):
        """Properly close the driver and cleanup resources"""
        try:
            if self.driver:
                logger.info("Closing browser...")
                try:
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"Error during driver.quit(): {e}")
                    # Force kill if quit fails
                    try:
                        self.driver.close()
                    except:
                        pass

                self.driver = None
                logger.info("Browser closed successfully")

                # Additional cleanup on Windows
                if os.name == 'nt':
                    try:
                        import subprocess
                        # Kill any remaining chrome/chromedriver processes
                        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'],
                                     capture_output=True, timeout=2)
                        time.sleep(0.5)
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error during driver cleanup: {e}")

    def __enter__(self):
        self.setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def save_to_json(products: List[Product], filename: str = "kilimall_products.json"):
    """Save products to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([product.__dict__ for product in products], f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(products)} products to {filename}")
    except Exception as e:
        logger.error(f"Error saving to JSON: {e}")

def main():
    """Main function for testing"""
    parser = argparse.ArgumentParser(description='Scrape products from Kilimall Kenya')
    parser.add_argument('--search', type=str, help='Search query for products')
    parser.add_argument('--category', type=str, help='Category URL to scrape')
    parser.add_argument('--pages', type=int, default=2, help='Number of pages to scrape (default: 2)')
    parser.add_argument('--output', type=str, default='kilimall_products.json', help='Output filename')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')

    args = parser.parse_args()

    if not args.search and not args.category:
        parser.error("Please provide either --search or --category")

    def progress_update(message, progress):
        print(f"Progress: {progress:.1f}% - {message}")

    with KilimallScraper(headless=args.headless) as scraper:
        if args.category:
            print(f"Scraping category: {args.category}")
            products = scraper.scrape_category(args.category, max_pages=args.pages, progress_callback=progress_update)
        else:
            print(f"Searching for: {args.search}")
            products = scraper.search_products(args.search, max_pages=args.pages, progress_callback=progress_update)

        if products:
            save_to_json(products, args.output)
            print(f"\nSuccessfully scraped {len(products)} products!")
            for i, product in enumerate(products[:5], 1):  # Show first 5
                print(f"{i}. {product.name} - {product.price}")
        else:
            print("No products found!")

if __name__ == "__main__":
    main()