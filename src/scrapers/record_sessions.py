import os
import json
from playwright.sync_api import sync_playwright

# Папка для збереження токенів та куків магазинів
SESSIONS_DIR = os.path.join(os.getcwd(), "browser_sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

STORES_TO_RECORD = [
    {"name": "sephora_pl", "url": "https://www.sephora.pl"},
    {"name": "iherb", "url": "https://www.iherb.com"},
]

def record_store_session(store_name: str, target_url: str):
    session_file = os.path.join(SESSIONS_DIR, f"{store_name}_state.json")
    
    print(f"\n🚀 Відкриваємо браузер для: {store_name.upper()}")
    
    with sync_playwright() as p:
        # Запускаємо звичайний Chromium з можливістю візуальної взаємодії
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="pl-PL",
            timezone_id="Europe/Warsaw"
        )
        
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded")
        
        print(f"👉 Пройдіть перевірку Akamai/Captcha у браузері, виберіть потрібну локаль чи кукі.")
        input("⌨️  Після того як сторінка повністю завантажиться — НАТИСНИ ENTER ТУТ...");
        
        # Зберігаємо Cookies, localStorage та інші параметри контексту в JSON
        context.storage_state(path=session_file)
        print(f"✅ Сесію для {store_name} збережено у {session_file}")
        
        browser.close()

if __name__ == "__main__":
    for store in STORES_TO_RECORD:
        record_store_session(store["name"], store["url"])