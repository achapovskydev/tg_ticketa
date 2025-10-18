#!/usr/bin/env python3
"""
tce_telegram_monitor.py
Мониторит tce.by/search.html по запросу SEARCH_TEXT и шлёт сообщение в Telegram,
если найдено более 3 записей в #playbill tbody tr.
"""

import os
import time
import logging
from dotenv import load_dotenv
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# Загрузка .env
load_dotenv()

BOT_TOKEN = os.getenv("7348919449:AAEDdogDWEp1N75iYVPWrniojpirRYAsnJg")
CHAT_ID = os.getenv("4824337407")
SEARCH_TEXT = os.getenv("SEARCH_TEXT", "Записки юного врача")
URL = os.getenv("URL", "https://tce.by/search.html")
# Опционально: порог, при превышении которого шлём уведомление
THRESHOLD = int(os.getenv("THRESHOLD", "3"))

# Логи
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("tce_monitor.log"),
        logging.StreamHandler()
    ]
)

def send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("BOT_TOKEN или CHAT_ID не заданы.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        r.raise_for_status()
        logging.info("Сообщение отправлено в Telegram.")
        return True
    except Exception as e:
        logging.exception("Ошибка отправки в Telegram: %s", e)
        return False

def get_count_with_selenium() -> int:
    options = Options()
    # headless
    options.add_argument("--headless=new")  # new headless for modern Chrome, fallback may be needed
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1200,800")
    options.add_argument("--ignore-certificate-errors")
    # Запуск chromedriver через webdriver-manager
    service = ChromeService(ChromeDriverManager().install())
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(URL)

        wait = WebDriverWait(driver, 20)
        input_box = wait.until(EC.presence_of_element_located((By.NAME, "tags")))
        input_box.clear()
        input_box.send_keys(SEARCH_TEXT)

        reload_btn = driver.find_element(By.ID, "reload")
        reload_btn.click()

        # Ждём либо появления строк, либо таймаут (если нет результатов строки могут не появиться)
        try:
            wait_short = WebDriverWait(driver, 10)
            wait_short.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#playbill tbody tr")))
        except TimeoutException:
            # Если нет tr — возможно 0 результатов
            logging.info("Нет <tr> после ожидания -> считаем 0.")
            return 0

        rows = driver.find_elements(By.CSS_SELECTOR, "#playbill tbody tr")
        count = len(rows)
        logging.info("Найдено %d тр.", count)
        return count
    except WebDriverException as e:
        logging.exception("WebDriver ошибка: %s", e)
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def main_once():
    try:
        count = get_count_with_selenium()
    except Exception as e:
        logging.exception("Ошибка при получении данных: %s", e)
        # можно отправить уведомление об ошибке (по желанию)
        send_telegram(f"❗ Ошибка мониторинга: {e}")
        return

    if count > THRESHOLD:
        text = (
            f"⚠️ <b>Найдено {count} мероприятий</b>\n\n"
            f"По запросу: <i>{SEARCH_TEXT}</i>\n{URL}"
        )
        send_telegram(text)
    else:
        logging.info("Порог (%d) не превышен (%d).", THRESHOLD, count)

if __name__ == "__main__":
    # Если хочешь запускать бесконечно внутри скрипта, можно раскомментировать:
    # interval = int(os.getenv("CHECK_INTERVAL", "600"))
    # while True:
    #     main_once()
    #     time.sleep(interval)

    # Рекомендуемый режим: запускать через cron каждые 10 минут.
    main_once()
