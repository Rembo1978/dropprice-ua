# scrapers/utils.py
from urllib.parse import urlparse

def extract_store_base_url(url: str) -> str:
    """
    З https://aliexpress.com/pl/item/100500.html витягує: https://aliexpress.com/pl/
    З https://www.ceneo.pl/169448807 витягує: https://www.ceneo.pl/
    """
    parsed = urlparse(url)
    scheme_netloc = f"{parsed.scheme}://{parsed.netloc}"
    
    path_parts = [p for p in parsed.path.split('/') if p]
    
    # Перевіряємо, чи перша частина шляху схожа на мовний префікс (pl, ua, en, de, pl-pl)
    if path_parts and len(path_parts[0]) <= 5 and not path_parts[0].endswith(('.html', '.php', '.asp')):
        return f"{scheme_netloc}/{path_parts[0]}/"
    
    return f"{scheme_netloc}/"