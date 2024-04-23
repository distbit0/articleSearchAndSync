import os
import ssl
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import requests
from selenium import webdriver
from urllib.parse import urlparse
from utils import getConfig
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import markdown


requests.packages.urllib3.disable_warnings()


def save_text_as_html(url, saveDirectory):
    response = requests.get(url, verify=ssl.CERT_NONE)
    text_content = response.text

    # Convert text to HTML using markdown
    html_content = markdown.markdown(text_content)

    parsed_url = urlparse(url)
    title = os.path.basename(parsed_url.path)
    title = "".join(c for c in title if c.isalnum() or c.isspace()).rstrip()

    html_content = f"<!-- Hyperionics-OriginHtml {url}-->\n{html_content}"

    file_path = os.path.join(saveDirectory, f"{title}.html")
    if os.path.exists(file_path):
        currentTime = int(time.time())
        file_path = file_path.replace(".html", f"_{currentTime}.html")

    with open(file_path, "w") as file:
        file.write(html_content)


def downloadNewArticles(urlsToAdd):
    saveDirectory = getConfig()["pdfSourceFolders"][0]
    print(urlsToAdd)
    for url in urlsToAdd:
        save_mobile_article_as_mhtml(url, saveDirectory)


def save_webpage_as_mhtml(url, saveDirectory, timeout=10, min_load_time=5):
    chrome_options = Options()
    user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        start_time = time.time()
        driver.get(url)
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        body_load_time = time.time() - start_time
        remaining_time = max(0, min_load_time - body_load_time)
        time.sleep(remaining_time)

        title = driver.title
        title = "".join(c for c in title if c.isalnum() or c.isspace()).rstrip()
        file_path = os.path.join(saveDirectory, f"{title}_mobile.mhtml")

        driver.execute_cdp_cmd("Page.captureSnapshot", {"format": "mhtml"})
        mhtml_data = driver.execute_cdp_cmd(
            "Page.captureSnapshot", {"format": "mhtml"}
        )["data"]

        mhtml_data = f"<!-- Hyperionics-OriginHtml {url}-->\n{mhtml_data}"

        if os.path.exists(file_path):
            currentTime = int(time.time())
            file_path = file_path.replace(".mhtml", f"_{currentTime}.mhtml")

        with open(file_path, "wb") as file:
            file.write(mhtml_data.encode("utf-8"))
    finally:
        driver.quit()


def save_mobile_article_as_mhtml(url, saveDirectory, timeout=10, min_load_time=5):
    try:
        response = requests.get(url, verify=False)
    except requests.exceptions.SSLError:
        url = url.replace("https", "http")
        response = requests.get(url, verify=False)

    content_type = response.headers.get("Content-Type")
    content_disposition = response.headers.get("Content-Disposition")

    if content_type == "text/plain" or (
        content_disposition and "attachment" in content_disposition
    ):
        print(f"saving url: {url} as text")
        save_text_as_html(url, saveDirectory)
    else:
        print(f"saving url: {url} as webpage")
        save_webpage_as_mhtml(url, saveDirectory, timeout, min_load_time)


if __name__ == "__main__":
    articles = """https://embeddedsw.net/doc/physical_coercion.txt
https://docs.google.com/document/d/1RgUr4dGAcfqmzQR8Ceym5QcfvrD8jGbGnrr4whkvDmU/export?format=txt
https://docs.google.com/document/d/1tza0OIdTZNNjTqhkWZLRC9ha9Sp7lumGF5ytthx_Ozw/export?format=txt"""
    downloadNewArticles(articles.split("\n"))
