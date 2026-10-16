# src/scrapers/services.py
import json
import os
import re
import traceback
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
from products.models import Product, Brand, PriceHistory
import concurrent.futures
from stores.models import Store, StoreSession, StoreError
from trackers.models import UserTracker
from users.models import UserSession
from decimal import Decimal
from typing import Optional, Tuple
from django.db import transaction
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import json
import os
import re
import asyncio
import traceback
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin
from bs4 import BeautifulSoup
from curl_cffi import requests
from playwright.sync_api import sync_playwright
import nodriver as uc
from scrapers.utils import extract_store_base_url
import html
# ==============================================================================
#  Утиліти обробки URL
# ==============================================================================

def quick_clean_url(url: str) -> str:
    """Швидко видаляє query-параметри (UTM-мітки) з URL без завантаження сторінки."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, '', '', ''))


def extract_canonical_url(html_content: str, fallback_url: str) -> str:
    """
    Витягує точний канонічний URL із вмісту HTML-сторінки.
    Пріоритет: JSON-LD -> <link rel="canonical"> -> <meta property="og:url">
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. JSON-LD (<script type="application/ld+json">)
    json_ld_scripts = soup.find_all('script', type=lambda t: t and 'ld+json' in str(t).lower())
    for script in json_ld_scripts:
        try:
            raw_text = script.string or script.get_text() or (script.contents[0] if script.contents else '')
            if not raw_text.strip():
                continue
            data = json.loads(raw_text.strip())
            items = data if isinstance(data, list) else [data]
            
            for item in items:
                if isinstance(item, dict) and item.get('@type') == 'Product':
                    offers = item.get('offers')
                    if isinstance(offers, dict) and offers.get('url'):
                        return offers['url']
                    elif isinstance(offers, list) and len(offers) > 0 and isinstance(offers[0], dict) and offers[0].get('url'):
                        return offers[0]['url']
                    
                    if item.get('url'):
                        return item['url']
        except (json.JSONDecodeError, TypeError, KeyError, IndexError):
            continue

    # 2. <link rel="canonical">
    canonical_tag = soup.find('link', rel=lambda r: r and 'canonical' in r.lower())
    if canonical_tag and canonical_tag.get('href'):
        return canonical_tag['href']

    # 3. <meta property="og:url">
    og_url = soup.find('meta', property='og:url')
    if og_url and og_url.get('content'):
        return og_url['content']

    # 4. Фолбек
    return quick_clean_url(fallback_url)


# ==============================================================================
#  Універсальний Скрапер
# ==============================================================================

class UniversalProductScraper:
    MAX_POSTGRES_PRICE = Decimal('99999999.99')

    def __init__(self, store: Optional[Store] = None):
        self.store = store
        # TLS Impersonate для первинних швидких запитів без браузера
        self.session = curl_requests.Session(impersonate="chrome120")
        self.headers = {
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # Токен та URL для підключення до Docker-контейнера Browserless
        self.browserless_token = os.getenv("BROWSERLESS_TOKEN", "your_secret_token_here")
        self.browserless_host = os.getenv("BROWSERLESS_HOST", "localhost:3000")

    # def fetch_product_data(self, url: str) -> Optional[Dict[str, Any]]:
    #     domain = self._extract_domain(url)
    #     store = self.store or Store.objects.get_or_create(domain=domain, defaults={"name": domain})[0]

    #     html_content = None

    #     # 1. Спроба завантаження: Fast curl_cffi vs Playwright (Browserless)
    #     if hasattr(store, 'requires_js') and store.requires_js:
    #         html_content = self._fetch_with_playwright(store, url)
    #     else:
    #         try:
    #             response = self.session.get(url, headers=self.headers, timeout=15, allow_redirects=True)
                
    #             if self._is_js_required_response(response):
    #                 print(f"[Auto-Detect] Магазин {domain} потребує JS. Перемикаємось на Browserless...")
    #                 store.requires_js = True
    #                 store.save(update_fields=['requires_js'])
    #                 html_content = self._fetch_with_playwright(store, url)
    #             elif response.status_code == 200:
    #                 html_content = response.text
    #             elif response.status_code in (403, 400, 503, 429):
    #                 print(f"[Scraper] HTTP {response.status_code} для {url}. Перемикаємось на Browserless...")
    #                 store.requires_js = True
    #                 store.save(update_fields=['requires_js'])
    #                 html_content = self._fetch_with_playwright(store, url)
    #             else:
    #                 print(f"[Scraper] Статус-код {response.status_code} для {url}")
    #                 StoreError.objects.create(
    #                     store=store,
    #                     url=url,
    #                     error_type=StoreError.ErrorType.HTTP_ERROR,
    #                     message=f"HTTP Status: {response.status_code}"
    #                 )
    #                 return None

    #         except Exception as e:
    #             print(f"[Scraper] Помилка curl_cffi для {url}: {e}. Перемикаємось на Browserless...")
    #             store.requires_js = True
    #             store.save(update_fields=['requires_js'])
    #             html_content = self._fetch_with_playwright(store, url)

    #     if not html_content:
    #         print(f"[Scraper] Не вдалося отримати HTML для {url}")
    #         return None

    #     # 2. Парсинг витягнутого HTML
    #     try:
    #         soup = BeautifulSoup(html_content, 'html.parser')
    #         json_ld_items = self._collect_json_ld_items(soup)

    #         data: Dict[str, Any] = {}
    #         data['store_domain'] = domain
    #         data['title'] = self._get_title(soup, json_ld_items)
    #         data['price'], data['currency'] = self._get_price_and_currency(soup, json_ld_items)
    #         data['description'] = self._get_description(soup, json_ld_items)

    #         raw_image = self._get_image_url(soup, json_ld_items)
    #         data['image_url'] = self._normalize_url(raw_image, base_url=url)
            
    #         data['is_in_stock'] = self._get_availability(soup, json_ld_items)
    #         data['brand_name'] = self._get_brand(soup, json_ld_items)
    #         data['gtin'] = self._get_gtin(soup, json_ld_items)

    #         # if not data.get('title') or data.get('price') is None:
    #         #     print(f"[Scraper] Не вдалося витягнути критичні поля (Title/Price) для {url}")
    #         #     StoreError.objects.create(
    #         #         store=store,
    #         #         url=url,
    #         #         error_type=StoreError.ErrorType.PARSING_FAILED,
    #         #         message="Missing mandatory fields: Title or Price"
    #         #     )
    #         #     return None
    #         if not data.get('title'):
    #             print(f"[Scraper] Не вдалося витягнути назву (Title) для {url}")
    #             StoreError.objects.create(
    #                 store=store,
    #                 url=url,
    #                 error_type=StoreError.ErrorType.PARSING_FAILED,
    #                 message="Missing mandatory field: Title"
    #             )
    #             return None

    #         if data.get('price') is None:
    #             print(f"[Scraper] Не вдалося витягнути ціну (Price) для {url}")
    #             StoreError.objects.create(
    #                 store=store,
    #                 url=url,
    #                 error_type=StoreError.ErrorType.PARSING_FAILED,
    #                 message="Missing mandatory field: Price"
    #             )
    #             return None

    #         data['url'] = self._get_canonical_url(soup, json_ld_items, raw_url=url)
    #         data['raw_input_url'] = url
    #         return data

    #     except Exception as e:
    #         print(f"[Scraper] Критична помилка парсингу {url}: {repr(e)}")
    #         traceback.print_exc()
    #         StoreError.objects.create(
    #             store=store,
    #             url=url,
    #             error_type=StoreError.ErrorType.UNKNOWN,
    #             message=str(e)
    #         )
    #         return None
    def fetch_product_data(self, url: str) -> Optional[Dict[str, Any]]:
        domain = self._extract_domain(url)
        store = self.store or Store.objects.get_or_create(domain=domain, defaults={"name": domain})[0]

        html_content = None

        # 1. Завантаження первинної сторінки (Fast curl_cffi vs Playwright)
        if hasattr(store, 'requires_js') and store.requires_js:
            html_content = self._fetch_with_playwright(store, url)
        else:
            try:
                response = self.session.get(url, headers=self.headers, timeout=15, allow_redirects=True)
                
                if self._is_js_required_response(response):
                    print(f"[Auto-Detect] Магазин {domain} потребує JS. Перемикаємось на Browserless...")
                    store.requires_js = True
                    store.save(update_fields=['requires_js'])
                    html_content = self._fetch_with_playwright(store, url)
                elif response.status_code == 200:
                    html_content = response.text
                elif response.status_code in (403, 400, 503, 429):
                    print(f"[Scraper] HTTP {response.status_code} для {url}. Перемикаємось на Browserless...")
                    store.requires_js = True
                    store.save(update_fields=['requires_js'])
                    html_content = self._fetch_with_playwright(store, url)
                else:
                    print(f"[Scraper] Статус-код {response.status_code} для {url}")
                    StoreError.objects.create(
                        store=store,
                        url=url,
                        error_type=StoreError.ErrorType.HTTP_ERROR,
                        message=f"HTTP Status: {response.status_code}"
                    )
                    return None

            except Exception as e:
                print(f"[Scraper] Помилка curl_cffi для {url}: {e}. Перемикаємось на Browserless...")
                store.requires_js = True
                store.save(update_fields=['requires_js'])
                html_content = self._fetch_with_playwright(store, url)

        if not html_content:
            print(f"[Scraper] Не вдалося отримати HTML для {url}")
            return None

        # 2. Робимо первинний швидкий парсинг, щоб знайти українську альтернативу (hreflang)
        temp_soup = BeautifulSoup(html_content, 'html.parser')
        uk_alternative_url = None
        for link in temp_soup.find_all('link', rel=lambda r: r and 'alternate' in r.lower()):
            hreflang = str(link.get('hreflang', '')).lower()
            if hreflang in ['uk', 'uk-ua']:
                href = link.get('href')
                if href:
                    uk_alternative_url = self._normalize_url(href, base_url=url)
                    break

        # Якщо знайшли українську версію і вона відрізняється від введеної користувачем
        if uk_alternative_url and quick_clean_url(uk_alternative_url) != quick_clean_url(url):
            print(f"[Scraper] Знайдено українську версію сторінки: {uk_alternative_url}. Переходимо за нею...")
            
            # Повторюємо завантаження вже для українського URL (враховуючи налаштування JS магазину)
            if store.requires_js:
                uk_html_content = self._fetch_with_playwright(store, uk_alternative_url)
            else:
                try:
                    uk_response = self.session.get(uk_alternative_url, headers=self.headers, timeout=15, allow_redirects=True)
                    if uk_response.status_code == 200:
                        uk_html_content = uk_response.text
                    else:
                        uk_html_content = self._fetch_with_playwright(store, uk_alternative_url)
                except Exception:
                    uk_html_content = self._fetch_with_playwright(store, uk_alternative_url)
            
            if uk_html_content:
                html_content = uk_html_content
                url = uk_alternative_url  # Оновлюємо робочий URL на український

        # 3. Основний парсинг фінального HTML (за українським або початковим URL)
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            json_ld_items = self._collect_json_ld_items(soup)

            data: Dict[str, Any] = {}
            data['store_domain'] = domain
            data['title'] = self._get_title(soup, json_ld_items)
            data['price'], data['currency'] = self._get_price_and_currency(soup, json_ld_items)
            data['description'] = self._get_description(soup, json_ld_items)

            raw_image = self._get_image_url(soup, json_ld_items)
            data['image_url'] = self._normalize_url(raw_image, base_url=url)
            
            data['is_in_stock'] = self._get_availability(soup, json_ld_items)
            data['brand_name'] = self._get_brand(soup, json_ld_items)
            data['gtin'] = self._get_gtin(soup, json_ld_items)

            if not data.get('title'):
                print(f"[Scraper] Не вдалося витягнути назву (Title) для {url}")
                StoreError.objects.create(
                    store=store,
                    url=url,
                    error_type=StoreError.ErrorType.PARSING_FAILED,
                    message="Missing mandatory field: Title"
                )
                return None

            if data.get('price') is None:
                print(f"[Scraper] Не вдалося витягнути ціну (Price) {url}")
                StoreError.objects.create(
                    store=store,
                    url=url,
                    error_type=StoreError.ErrorType.PARSING_FAILED,
                    message="Missing mandatory field: Price"
                )
                return None

            data['url'] = self._get_canonical_url(soup, json_ld_items, raw_url=url)
            data['raw_input_url'] = url
            return data

        except Exception as e:
            print(f"[Scraper] Критична помилка парсингу {url}: {repr(e)}")
            traceback.print_exc()
            StoreError.objects.create(
                store=store,
                url=url,
                error_type=StoreError.ErrorType.UNKNOWN,
                message=str(e)
            )
            return None
    # ------------------------------------------------------------------
    #  Методи завантаження через Browserless Docker Container
    # ------------------------------------------------------------------
    def _extract_domain(self, url: str) -> str:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc

    def _get_active_session_data(self, store: Store) -> Optional[dict]:
        try:
            session = StoreSession.objects.get(store=store, is_expired=False)
            return session.session_data
        except StoreSession.DoesNotExist:
            return None

    def _prepare_playwright_cookies(self, raw_cookies: list) -> list:
        formatted_cookies = []
        for c in raw_cookies:
            same_site = c.get('sameSite', 'Lax')
            if same_site not in ['Strict', 'Lax', 'None']:
                same_site = 'Lax'
                
            cookie_dict = {
                'name': c['name'],
                'value': str(c['value']),
                'domain': c['domain'],
                'path': c.get('path', '/'),
                'secure': c.get('secure', True),
                'httpOnly': c.get('httpOnly', False),
                'sameSite': same_site
            }
            if c.get('expires') and c['expires'] > 0:
                cookie_dict['expires'] = float(c['expires'])
                
            formatted_cookies.append(cookie_dict)
        return formatted_cookies

    # def _fetch_with_playwright(self, store: Store, url: str) -> Optional[str]:
    #     session_data = self._get_active_session_data(store)
        
    #     # Передаємо параметри для заплутування FingerprintJS
    #     ws_endpoint = (
    #         f"ws://{self.browserless_host}"
    #         f"?token={self.browserless_token}"
    #         f"&stealth"
    #         f"&--disable-blink-features=AutomationControlled"
    #         f"&--no-sandbox"
    #     )

    #     try:
    #         with sync_playwright() as p:
    #             browser = p.chromium.connect_over_cdp(ws_endpoint)

    #             # Створюємо контекст з підміною реальних характеристик пристрою
    #             context = browser.new_context(
    #                 viewport={'width': 1920, 'height': 1080},
    #                 screen={'width': 1920, 'height': 1080},
    #                 user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    #                 locale="uk-UA",
    #                 timezone_id="Europe/Kyiv",
    #                 device_scale_factor=1,
    #                 has_touch=False,
    #                 is_mobile=False,
    #                 color_scheme='light',
    #             )

    #             if session_data and "cookies" in session_data:
    #                 formatted = self._prepare_playwright_cookies(session_data["cookies"])
    #                 context.add_cookies(formatted)

    #             page = context.new_page()

    #             # Скрипт-антифінгерпринт: підміна атрибутів, які перевіряє FingerprintJS
    #             page.add_init_script("""
    #                 // 1. Приховуємо факт автоматизації
    #                 Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    #                 // 2. Емуляція плагінів (у headless за замовчуванням порожній масив)
    #                 Object.defineProperty(navigator, 'plugins', {
    #                     get: () => [1, 2, 3, 4, 5]
    #                 });

    #                 // 3. Підміна мов
    #                 Object.defineProperty(navigator, 'languages', {
    #                     get: () => ['uk-UA', 'uk', 'en-US', 'en']
    #                 });

    #                 // 4. Шуми для WebGL Fingerprint (захист від WebGL трекінгу)
    #                 const getParameter = WebGLRenderingContext.prototype.getParameter;
    #                 WebGLRenderingContext.prototype.getParameter = function(parameter) {
    #                     // UNMASKED_VENDOR_WEBGL
    #                     if (parameter === 37445) return 'Google Inc. (NVIDIA)';
    #                     // UNMASKED_RENDERER_WEBGL
    #                     if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    #                     return getParameter.apply(this, arguments);
    #                 };
    #             """)

    #             # Перехід на сторінку
    #             response = page.goto(url, wait_until="networkidle", timeout=45000)
                
    #             # Поведінка людини для спрацювання JS-скриптів
    #             page.wait_for_timeout(2000)
    #             page.mouse.move(100, 200)
    #             page.mouse.wheel(0, 400)
    #             page.wait_for_timeout(1500)

    #             content = page.content()
                
    #             context.close()
    #             browser.close()
    #             return content

    #     except Exception as e:
    #         print(f"[Browserless Error] Не вдалося обійти FingerprintJS для {url}: {e}")
    #         return None
    def _fetch_with_playwright(self, store: Store, url: str) -> Optional[str]:
        session_data = self._get_active_session_data(store)
        
        ws_endpoint = (
            f"ws://{self.browserless_host}"
            f"?token={self.browserless_token}"
            f"&stealth"
            f"&--disable-blink-features=AutomationControlled"
            f"&--no-sandbox"
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(ws_endpoint)

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    screen={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    locale="uk-UA",
                    timezone_id="Europe/Kyiv",
                    device_scale_factor=1,
                    has_touch=False,
                    is_mobile=False,
                    color_scheme='light',
                )

                if session_data and "cookies" in session_data:
                    formatted = self._prepare_playwright_cookies(session_data["cookies"])
                    context.add_cookies(formatted)

                page = context.new_page()

                # Антифінгерпринт скрипти (вже є у вашому коді)
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['uk-UA', 'uk', 'en-US', 'en'] });
                """)

                # Перехід на сторінку товару
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Даємо час на виконання JS-челенджу Horoshop (якщо він є)
                page.wait_for_timeout(1500)

                # Перевіряємо, чи ми застрягли на сторінці з челенджем (challenge_passed)
                content = page.content()
                if "challenge_passed" in content or "performance.now()" in content:
                    print(f"[Scraper] Виявлено JS-челендж Horoshop для {url}. Проходимо...")
                    
                    # Виконуємо скрипт челенджу примусово через браузер, якщо він не спрацював автоматично
                    page.evaluate("""
                        () => {
                            const defaultHash = "7b94bd83bafef4440599990f2fdc28b10c157005de48489bd01d20e06cd12182";
                            document.cookie = "challenge_passed=" + defaultHash + "; max-age=1800; path=/; samesite=Lax";
                        }
                    """)
                    
                    # Перезавантажуємо сторінку вже з встановленою кукою
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1500)
                    content = page.content()

                # Імітація поведінки людини
                page.mouse.move(100, 200)
                page.mouse.wheel(0, 400)
                page.wait_for_timeout(1000)

                final_content = page.content()
                
                context.close()
                browser.close()
                return final_content

        except Exception as e:
            print(f"[Browserless Error] Не вдалося обійти захист для {url}: {e}")
            return None

    # ------------------------------------------------------------------
    #  Збір та очищення JSON-LD / HTML
    # ------------------------------------------------------------------
    # def _collect_json_ld_items(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
    #     items = []
    #     scripts = soup.find_all('script', type=lambda t: t and 'ld+json' in str(t).lower())
        
    #     for script in scripts:
    #         raw_text = script.string or script.get_text() or (script.contents[0] if script.contents else '')
    #         if not raw_text or not raw_text.strip():
    #             continue
            
    #         payload = self._safe_json_parse(raw_text.strip())
    #         if not payload:
    #             continue

    #         nodes = payload if isinstance(payload, list) else [payload]
    #         for node in nodes:
    #             if isinstance(node, dict):
    #                 if '@graph' in node and isinstance(node['@graph'], list):
    #                     items.extend([g for g in node['@graph'] if isinstance(g, dict)])
    #                 else:
    #                     items.append(node)
    #     return items
    def _collect_json_ld_items(
        self, soup: BeautifulSoup
    ) -> List[Dict[str, Any]]:

        scripts = soup.find_all(
            'script',
            type=lambda t: t and 'ld+json' in str(t).lower()
        )

        # Резервна спроба, якщо HTML-теги теж екрановані.
        if not scripts:
            decoded_html = html.unescape(str(soup))
            decoded_soup = BeautifulSoup(decoded_html, 'html.parser')

            scripts = decoded_soup.find_all(
                'script',
                type=lambda t: t and 'ld+json' in str(t).lower()
            )

            if scripts:
                soup = decoded_soup

        items = []

        for script in scripts:
            raw_text = script.string or script.get_text() or ''

            if not raw_text.strip():
                continue

            payload = self._safe_json_parse(raw_text)

            if payload is None:
                continue

            nodes = payload if isinstance(payload, list) else [payload]

            for node in nodes:
                if not isinstance(node, dict):
                    continue

                if isinstance(node.get('@graph'), list):
                    items.extend(
                        g for g in node['@graph']
                        if isinstance(g, dict)
                    )
                else:
                    items.append(node)

        return items

    # def _safe_json_parse(self, text: str) -> Optional[Any]:
    #     try:
    #         return json.loads(text)
    #     except json.JSONDecodeError:
    #         pass

    #     try:
    #         sanitized = re.sub(r'("<a href=)"([^"]*)"([^>]*>)', r"\1'\2'\3", text)
    #         sanitized = re.sub(r'[\r\n\t]+', ' ', sanitized)
    #         return json.loads(sanitized)
    #     except Exception:
    #         return None
    def _safe_json_parse(self, text: str) -> Optional[Any]:
        if not text:
            return None

        raw = text.strip()

        # Спочатку пробуємо звичайний JSON,
        # потім JSON з HTML-сутностями.
        candidates = [raw, html.unescape(raw)]

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        return None
    def _clean_price(self, raw_val: Any) -> Optional[Decimal]:
        if raw_val is None:
            return None
        try:
            val_str = str(raw_val).replace('\xa0', '').replace(' ', '').replace(',', '.')
            match = re.search(r'\d+(?:\.\d+)?', val_str)
            if not match:
                return None
            
            price = Decimal(match.group(0))
            if price <= Decimal('0') or price > self.MAX_POSTGRES_PRICE:
                return None
                
            return price.quantize(Decimal('0.01'))
        except Exception:
            return None

    def _get_meta(self, soup: BeautifulSoup, key: str) -> Optional[str]:
        keys_to_check = [key, key.lower()]
        for k in keys_to_check:
            tag = (
                soup.find('meta', attrs={'property': k}) or
                soup.find('meta', attrs={'name': k}) or
                soup.find('meta', attrs={'itemprop': k}) or
                soup.find('meta', attrs={'itemProp': k})
            )
            if tag and tag.get('content'):
                return tag.get('content').strip()
        return None

    # ------------------------------------------------------------------
    #  Парсинг конкретних полів
    # ------------------------------------------------------------------
    # def _get_title(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
    #     for item in json_ld_items:
    #         itype = str(item.get('@type', '')).lower()
    #         if any(t in itype for t in ['product', 'productgroup', 'individualproduct']):
    #             if item.get('name'):
    #                 return str(item['name']).strip()
        
    #     og_title = self._get_meta(soup, 'og:title') or self._get_meta(soup, 'twitter:title')
    #     if og_title:
    #         return og_title.strip()
        
    #     h1 = soup.find('h1')
    #     return h1.text.strip() if h1 else None

    #     # В останню чергу шукаємо звичайний тег <title>
    #     title_tag = soup.find('title')
    #     return title_tag.text.strip() if title_tag else None
    def _get_title(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
        for item in json_ld_items:
            itype = str(item.get('@type', '')).lower()
            if any(t in itype for t in ['product', 'productgroup', 'individualproduct']):
                if item.get('name'):
                    return str(item['name']).strip()
        
        og_title = self._get_meta(soup, 'og:title') or self._get_meta(soup, 'twitter:title')
        if og_title:
            return og_title.strip()
        
        h1 = soup.find('h1')
        if h1 and h1.text.strip():
            return h1.text.strip()
            
        # В останню чергу шукаємо звичайний тег <title>
        title_tag = soup.find('title')
        return title_tag.text.strip() if title_tag else None

    def _extract_price_from_price_spec(self, price_spec: Any) -> Tuple[Optional[Decimal], Optional[str]]:
        specs = []
        if isinstance(price_spec, dict):
            specs = [price_spec]
        elif isinstance(price_spec, list):
            specs = [s for s in price_spec if isinstance(s, dict)]

        if not specs:
            return None, None

        for spec in specs:
            price_type = str(spec.get('priceType', ''))
            if 'saleprice' in price_type.lower():
                cleaned = self._clean_price(spec.get('price'))
                if cleaned:
                    return cleaned, spec.get('priceCurrency')

        for spec in specs:
            cleaned = self._clean_price(spec.get('price'))
            if cleaned:
                return cleaned, spec.get('priceCurrency')

        return None, None

    # def _get_price_and_currency(
    #     self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]
    # ) -> Tuple[Optional[Decimal], str]:
    #     currency = 'UAH'

    #     for target in json_ld_items:
    #         if not isinstance(target, dict):
    #             continue

    #         itype = str(target.get('@type', '')).lower()
    #         if any(t in itype for t in ['product', 'productgroup', 'individualproduct', 'offer']):
    #             offers = target if 'offer' in itype else target.get('offers')

    #             if not offers and 'hasVariant' in target:
    #                 variants = target['hasVariant']
    #                 if isinstance(variants, list) and variants and isinstance(variants[0], dict):
    #                     offers = variants[0].get('offers')

    #             offer_list = []
    #             if isinstance(offers, dict):
    #                 offer_list = [offers]
    #             elif isinstance(offers, list):
    #                 offer_list = [o for o in offers if isinstance(o, dict)]

    #             for offer in offer_list:
    #                 raw_p = offer.get('price') or offer.get('lowPrice')
    #                 price_spec = offer.get('priceSpecification')

    #                 parsed_price = self._clean_price(raw_p)
    #                 parsed_curr = offer.get('priceCurrency')

    #                 if parsed_price is None and price_spec:
    #                     spec_price, spec_curr = self._extract_price_from_price_spec(price_spec)
    #                     if spec_price:
    #                         parsed_price = spec_price
    #                         if spec_curr:
    #                             parsed_curr = spec_curr

    #                 if parsed_price is not None:
    #                     if parsed_curr:
    #                         currency = parsed_curr
    #                     return parsed_price, currency

    #     raw_meta_price = (
    #         self._get_meta(soup, 'product:sale_price:amount') or 
    #         self._get_meta(soup, 'product:price:amount') or 
    #         self._get_meta(soup, 'og:price:amount') or
    #         self._get_meta(soup, 'price') or
    #         self._get_meta(soup, 'twitter:data1')
    #     )
        
    #     meta_curr = (
    #         self._get_meta(soup, 'priceCurrency') or
    #         self._get_meta(soup, 'product:price:currency') or 
    #         self._get_meta(soup, 'og:price:currency')
    #     )
    #     if meta_curr:
    #         currency = meta_curr

    #     if raw_meta_price:
    #         price = self._clean_price(raw_meta_price)
    #         if price is not None:
    #             return price, currency

    #     price_patterns = [
    #         {'itemprop': re.compile(r'^price$', re.I)},
    #         {'class_': re.compile(r'(product-price|current-price|price-new|main-price|price)', re.I)},
    #         {'id': re.compile(r'(product-price|price-block|mainPrice)', re.I)}
    #     ]

    #     for pattern in price_patterns:
    #         elements = soup.find_all(**pattern)
    #         for element in elements:
    #             content = element.get('content') or element.get_text(strip=True)
    #             cleaned = self._clean_price(content)
    #             if cleaned:
    #                 return cleaned, currency

    #     return None, currency
    def _get_price_and_currency(
        self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]
    ) -> Tuple[Optional[Decimal], str]:
        currency = 'UAH'

        # Прямий глибокий пошук цін у будь-якому блоці JSON-LD (ігноруючи тип ноди, якщо там є ціна)
        all_offers = []
        for item in json_ld_items:
            if not isinstance(item, dict):
                continue
            
            # Якщо сам елемент є оффером або містить ціну
            if 'price' in item:
                all_offers.append(item)
                
            # Якщо всередині є offers
            offers = item.get('offers')
            if isinstance(offers, dict):
                all_offers.append(offers)
            elif isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict):
                        all_offers.append(o)
                        
            # Перевірка hasVariant
            variants = item.get('hasVariant')
            if isinstance(variants, list):
                for var in variants:
                    if isinstance(var, dict):
                        var_offers = var.get('offers')
                        if isinstance(var_offers, dict):
                            all_offers.append(var_offers)
                        elif isinstance(var_offers, list):
                            all_offers.extend([vo for vo in var_offers if isinstance(vo, dict)])

        # 1. Шукаємо серед усіх зібраних офферів той, що в наявності (InStock)
        for offer in all_offers:
            availability = str(offer.get('availability', '')).lower()
            if 'instock' in availability:
                raw_p = offer.get('price') or offer.get('lowPrice')
                parsed_price = self._clean_price(raw_p)
                if parsed_price is not None:
                    if offer.get('priceCurrency'):
                        currency = offer.get('priceCurrency')
                    return parsed_price, currency

        # 2. Якщо InStock не знайдено, беремо першу ліпшу ціну з усіх знайдених
        for offer in all_offers:
            raw_p = offer.get('price') or offer.get('lowPrice')
            price_spec = offer.get('priceSpecification')

            parsed_price = self._clean_price(raw_p)
            parsed_curr = offer.get('priceCurrency')

            if parsed_price is None and price_spec:
                spec_price, spec_curr = self._extract_price_from_price_spec(price_spec)
                if spec_price:
                    parsed_price = spec_price
                    if spec_curr:
                        parsed_curr = spec_curr

            if parsed_price is not None:
                if parsed_curr:
                    currency = parsed_curr
                return parsed_price, currency

        # Фолбеки на мета-теги та звичайні CSS-селектори
        raw_meta_price = (
            self._get_meta(soup, 'product:sale_price:amount') or 
            self._get_meta(soup, 'product:price:amount') or 
            self._get_meta(soup, 'og:price:amount') or
            self._get_meta(soup, 'price') or
            self._get_meta(soup, 'twitter:data1')
        )
        
        meta_curr = (
            self._get_meta(soup, 'priceCurrency') or
            self._get_meta(soup, 'product:price:currency') or 
            self._get_meta(soup, 'og:price:currency')
        )
        if meta_curr:
            currency = meta_curr

        if raw_meta_price:
            price = self._clean_price(raw_meta_price)
            if price is not None:
                return price, currency

        price_patterns = [
            {'itemprop': re.compile(r'^price$', re.I)},
            {'class_': re.compile(r'(product-price|current-price|price-new|main-price|price)', re.I)},
            {'id': re.compile(r'(product-price|price-block|mainPrice)', re.I)}
        ]

        for pattern in price_patterns:
            elements = soup.find_all(**pattern)
            for element in elements:
                content = element.get('content') or element.get_text(strip=True)
                cleaned = self._clean_price(content)
                if cleaned:
                    return cleaned, currency

        return None, currency

    def _get_availability(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> bool:
        for item in json_ld_items:
            offers = item.get('offers')
            if not offers and 'hasVariant' in item:
                variants = item['hasVariant']
                if isinstance(variants, list) and variants and isinstance(variants[0], dict):
                    offers = variants[0].get('offers')

            target_offer = None
            if isinstance(offers, dict):
                target_offer = offers
            elif isinstance(offers, list) and len(offers) > 0:
                for off in offers:
                    if isinstance(off, dict):
                        target_offer = off
                        break

            if target_offer:
                avail = target_offer.get('availability', '')
                if avail:
                    return 'instock' in str(avail).lower()

        og_avail = (
            self._get_meta(soup, 'product:availability') or 
            self._get_meta(soup, 'og:availability')
        )
        if og_avail:
            return og_avail.lower() in ['instock', 'in stock', 'true', '1']
        return True

    def _get_brand(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
        VALID_PRODUCT_TYPES = {'product', 'individualproduct', 'productmodel', 'someproducts', 'productgroup'}

        for item in json_ld_items:
            item_type = str(item.get('@type', '')).lower()
            if any(t in item_type for t in VALID_PRODUCT_TYPES):
                brand = item.get('brand')
                if isinstance(brand, dict):
                    name = brand.get('name')
                    if name and isinstance(name, str) and name.strip():
                        return name.strip()
                elif isinstance(brand, str) and brand.strip():
                    return brand.strip()

        meta_brand = self._get_meta(soup, 'product:brand') or self._get_meta(soup, 'og:brand')
        if meta_brand and meta_brand.strip():
            return meta_brand.strip()

        brand_element = soup.find(attrs={"itemprop": "brand"})
        if brand_element:
            name_meta = brand_element.find(attrs={"itemprop": "name"})
            if name_meta:
                brand_name = name_meta.get('content') or name_meta.get_text()
                if brand_name and brand_name.strip():
                    return brand_name.strip()
            
            fallback_name = brand_element.get('content') or brand_element.get_text()
            if fallback_name and fallback_name.strip():
                return fallback_name.strip()

        return None

    def _get_image_url(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
        for target in json_ld_items:
            if isinstance(target, dict) and any(t in str(target.get('@type', '')).lower() for t in ['product', 'productgroup']):
                img = target.get('image')
                url = self._parse_img_field(img)
                if url:
                    return url

        og_img = (
            self._get_meta(soup, 'og:image:secure_url') or 
            self._get_meta(soup, 'og:image') or
            self._get_meta(soup, 'twitter:image')
        )
        if og_img:
            return og_img

        main_img = soup.find('img', id=re.compile(r'(product|main)', re.I)) or soup.find('img', class_=re.compile(r'(product|main)', re.I))
        if main_img and main_img.get('src'):
            return main_img['src']

        return None

    def _get_gtin(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
        for item in json_ld_items:
            gtin = item.get('gtin13') or item.get('gtin8') or item.get('gtin') or item.get('gtin14')
            if gtin:
                if isinstance(gtin, list):
                    return ", ".join(str(g) for g in gtin if g)
                return str(gtin)
        return None

    def _get_description(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]]) -> Optional[str]:
        for item in json_ld_items:
            itype = str(item.get('@type', '')).lower()
            if any(t in itype for t in ['product', 'productgroup']) and item.get('description'):
                desc = item['description']
                if isinstance(desc, str) and desc.strip():
                    return BeautifulSoup(desc, 'html.parser').get_text(strip=True)

        og_desc = (
            self._get_meta(soup, 'og:description') or 
            self._get_meta(soup, 'description') or 
            self._get_meta(soup, 'twitter:description')
        )
        if og_desc:
            return og_desc.strip()

        desc_patterns = [
            {'id': re.compile(r'(product-description|description|tab-description)', re.I)},
            {'class_': re.compile(r'(product-description|description|product-detail-description)', re.I)},
            {'itemprop': 'description'}
        ]
        for pattern in desc_patterns:
            element = soup.find(**pattern)
            if element:
                cleaned_text = element.get_text(separator=' ', strip=True)
                if cleaned_text:
                    return cleaned_text
        return None

    # ------------------------------------------------------------------
    #  Утиліти обробки URL та атрибутів
    # ------------------------------------------------------------------
    def _is_js_required_response(self, response: Any) -> bool:
        if response.status_code in (403, 429, 503):
            return True

        html = response.text.lower()
        js_protection_patterns = [
            # 'just a moment...',
            # 'enable javascript',
            # 'cf-browser-verification',
            # 'chk_jschl',
            # 'ddos-guard',
            # 'access denied',
            # '<div id="app"></div>',
            # '<div id="root"></div>'
            'just a moment...',
            'enable javascript',
            'cf-browser-verification',
            'chk_jschl',
            'ddos-guard',
            'access denied',
            '<div id="app"></div>',
            '<div id="root"></div>',
            'challenge_passed',  # <--- Додаємо детект захисту Horoshop
            'performance.now()'  # <--- Додаємо детект циклу навантаження
        ]
        return any(pattern in html for pattern in js_protection_patterns)

    def _parse_img_field(self, img_field: Any) -> Optional[str]:
        if not img_field:
            return None
        if isinstance(img_field, list) and len(img_field) > 0:
            first_elem = img_field[0]
            if isinstance(first_elem, str):
                return first_elem
            if isinstance(first_elem, dict):
                return first_elem.get('url') or first_elem.get('contentUrl')
        if isinstance(img_field, str):
            return img_field
        if isinstance(img_field, dict):
            return img_field.get('url') or img_field.get('contentUrl')
        return None

    def _normalize_url(self, img_url: Optional[str], base_url: str) -> Optional[str]:
        if not img_url:
            return None
        img_url = img_url.strip()
        if img_url.startswith('//'):
            protocol = base_url.split('://')[0] if '://' in base_url else 'https'
            return f"{protocol}:{img_url}"
        if not (img_url.startswith('http://') or img_url.startswith('https://')):
            return urljoin(base_url, img_url)
        return img_url

    def _clean_utm_params(self, url: str) -> str:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'gclid', 'fbclid', 'yclid', '_ga', 'spm', 'ref', 'sessionid', 'sc_content'
        }
        filtered_params = {
            k: v for k, v in query_params.items() if k.lower() not in tracking_params
        }
        new_query = urlencode(filtered_params, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

    def _get_canonical_url(self, soup: BeautifulSoup, json_ld_items: List[Dict[str, Any]], raw_url: str) -> str:
        # 1. Пріоритет: пошук української альтернативної версії сторінки (hreflang="uk" або "uk-UA")
        for link in soup.find_all('link', rel=lambda r: r and 'alternate' in r.lower()):
            hreflang = str(link.get('hreflang', '')).lower()
            if hreflang in ['uk', 'uk-ua']:
                href = link.get('href')
                if href:
                    normalized = self._normalize_url(href, base_url=raw_url)
                    if normalized:
                        return normalized

        # 2. Канонічне посилання (<link rel="canonical">) — якщо української версії немає або сайт одномовний
        canonical_link = soup.find('link', rel=lambda r: r and 'canonical' in r.lower())
        if canonical_link and canonical_link.get('href'):
            return self._normalize_url(canonical_link['href'], base_url=raw_url) or raw_url

        # 3. Open Graph URL (og:url)
        og_url = self._get_meta(soup, 'og:url')
        if og_url:
            return self._normalize_url(og_url, base_url=raw_url) or raw_url

        # 4. JSON-LD дані (Product / ProductGroup)
        for item in json_ld_items:
            itype = str(item.get('@type', '')).lower()
            if any(t in itype for t in ['product', 'productgroup']) and item.get('url'):
                return self._normalize_url(item['url'], base_url=raw_url) or raw_url

        # 5. Фолбек: повертаємо вхідний URL без UTM-міток
        return self._clean_utm_params(raw_url)


class ProductSaveService:

    @classmethod
    @transaction.atomic
    def save_parsed_product(cls, data: Dict[str, Any], session_obj: UserSession) -> Product:
        """
        Приймає словник розпарсених даних від UniversalProductScraper та об'єкт UserSession.
        Зберігає/оновлює Store, Brand, Product, PriceHistory та повертає Product.
        """
        raw_url = data.get('url', '')
        canonical_url = data.get('canonical_url') or quick_clean_url(raw_url)

        store, _ = Store.get_or_create_from_url(canonical_url)

        brand = None
        brand_name = data.get('brand_name')
        if brand_name:
            brand, _ = Brand.get_or_create_by_name(brand_name)

        raw_price = data.get('price')
        price_decimal = Decimal(str(raw_price)) if raw_price is not None else None
        currency = data.get('currency') or 'UAH'
        is_in_stock = data.get('is_in_stock', True)

        product, created = Product.objects.get_or_create(
            url=canonical_url,
            defaults={
                'store': store,
                'brand': brand,
                'title': data.get('title') or '',
                'description': data.get('description') or '',
                'image_url': data.get('image_url') or '',
                'gtin': data.get('gtin') or '',
                'current_price': price_decimal,
                'currency': currency,
                'is_in_stock': is_in_stock,
            }
        )

        if not created:
            update_fields = []
            
            if data.get('title') and product.title != data['title']:
                product.title = data['title']
                update_fields.append('title')
                
            if data.get('image_url') and product.image_url != data['image_url']:
                product.image_url = data['image_url']
                update_fields.append('image_url')

            if product.is_in_stock != is_in_stock:
                product.is_in_stock = is_in_stock
                update_fields.append('is_in_stock')

            if data.get('gtin') and not product.gtin:
                product.gtin = data['gtin']
                update_fields.append('gtin')

            if brand and not product.brand:
                product.brand = brand
                update_fields.append('brand')

            if price_decimal is not None and product.current_price != price_decimal:
                old_price = product.current_price
                product.current_price = price_decimal
                update_fields.append('current_price')

                PriceHistory.objects.create(
                    product=product,
                    price=price_decimal,
                    old_price=old_price,
                    is_in_stock=is_in_stock
                )

            if update_fields:
                product.save(update_fields=update_fields)

        else:
            if price_decimal is not None:
                PriceHistory.objects.create(
                    product=product,
                    price=price_decimal,
                    old_price=None,
                    is_in_stock=is_in_stock
                )

        return product