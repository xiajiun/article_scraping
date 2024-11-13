import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import logging

def login_to_gartner(driver):
    # Open the login page
    driver.get("https://www.gartner.com/account/signin")

    try:
        # Wait for the login page to fully load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "loginFormWrapper"))
        )

        # Wait for the username field to be present and visible
        username_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "username"))
        )
        # Scroll to the username field to ensure it is in view
        driver.execute_script("arguments[0].scrollIntoView();", username_field)

        username_field.send_keys("username")  # Replace with your actual username

        # Wait for the password field to be present and visible
        password_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password"))
        )
        # Scroll to the password field to ensure it is in view
        driver.execute_script("arguments[0].scrollIntoView();", password_field)

        password_field.send_keys("password")  # Replace with your actual password

        # Wait for the login button to be clickable
        login_button = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "gSignInButton"))
        )
        # Scroll to the login button to ensure it is in view
        driver.execute_script("arguments[0].scrollIntoView();", login_button)
        login_button.click()

        # Wait until redirected to the main page after login
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Login successful.")

    except TimeoutException:
        print("Login failed: Timeout occurred while waiting for elements.")
    except NoSuchElementException:
        print("Login failed: Some elements required for login were not found or could not be interacted with.")
    except TimeoutException:
        print("Login failed: Timeout occurred while waiting for elements.")
    except NoSuchElementException:
        print("Login failed: Some elements required for login were not found or could not be interacted with.")


# Set up logging
logging.basicConfig(level=logging.INFO)

# Cache to store API responses
api_cache = {}

# Keywords to search for
KEYWORDS = [
    "medical AI", "AI", "pathology", "mammo", "deep learning", "medical",
    "chest x-ray", "mammography", "radiology", "machine learning", "computer-aided diagnosis",
    "digital radiology", "portable machine", "X-ray", "teleradiology", 'medical imaging', 'medical data', 'PACS'
]

# Base URL of the Gartner articles page
URL = "https://www.gartner.com/en/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36"
}
OUTPUT_FILE = "gartner_articles.xlsx"

def get_gartner_articles():
    # Set Firefox options to headless
    firefox_options = Options()
    firefox_options.add_argument("--headless")

    # Set up Firefox driver in headless mode
    driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=firefox_options)

    # Login to Gartner
    login_to_gartner(driver)

    # After login, navigate to the articles page
    driver.get(URL)

    articles = []

    try:
        title_tag = driver.find_element(By.TAG_NAME, "h1")
        title = title_tag.get_attribute("data-en-heading").strip() if title_tag.get_attribute("data-en-heading") else title_tag.text.strip()
        
        # Extract publication metadata
        metadata_tag = driver.find_element(By.CLASS_NAME, "p-xsmall")
        metadata_text = metadata_tag.text.strip()
        
        # Extract subheading from h3 tag
        try:
            subheading_tag = driver.find_element(By.CLASS_NAME, "h3")
            subheading = subheading_tag.text.strip()
        except NoSuchElementException:
            subheading = ""

        # Extract additional subheading from h2 tag
        try:
            h2_tag = driver.find_element(By.TAG_NAME, "h2")
            h2_text = h2_tag.text.strip()

            # Extract bullet points from the h2 tag's unordered list
            list_items = h2_tag.find_elements(By.TAG_NAME, "li")
            h2_points = " | ".join([item.text.strip() for item in list_items])
        except NoSuchElementException:
            h2_text = ""
            h2_points = ""

        # Extract content from the article tag
        try:
            content_tag = driver.find_element(By.CLASS_NAME, "article-text")
            content = content_tag.text.strip()
        except NoSuchElementException:
            content = ""

        link_tag = driver.find_element(By.TAG_NAME, "a")
        link = link_tag.get_attribute("href")

        # Print the link being scraped
        print(f"Scraping link: {link}")

        # Extract the publication date from metadata
        metadata_parts = metadata_text.split('|')
        if len(metadata_parts) >= 3:
            publication_date = metadata_parts[2].strip()
        else:
            publication_date = "Unknown"

        # Check if title, subheading, or h2 contains any of the keywords
        if any(keyword.lower() in title.lower() or keyword.lower() in subheading.lower() or keyword.lower() in h2_text.lower() for keyword in KEYWORDS):
            articles.append({
                "Date of article": publication_date,
                "Title": title,
                "Subheading": subheading,
                "H2": h2_text,
                "H2 Points": h2_points,
                "Content": content,
                "URL": link
            })

    except NoSuchElementException:
        # Skip if any of the required elements are missing
        pass

    # Close the browser
    driver.quit()
    return articles

def extract_sentences(content, keywords):
    sentences = content.split('.')
    related_sentences = [sentence.strip() for sentence in sentences if any(keyword.lower() in sentence.lower() for keyword in keywords)]
    return " | ".join(related_sentences)

def get_article_details(article_url):
    if article_url in api_cache:
        logging.info(f"Using cached data for {article_url}")
        return api_cache[article_url]
    else:
        response = requests.get(article_url, headers=HEADERS)
        if response.status_code != 200:
            logging.error(f"Failed to retrieve article page: {article_url}. Status code: {response.status_code}")
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.get_text(separator=' ', strip=True)
        api_cache[article_url] = content  # Cache the response
        return content

def load_existing_articles(file_path):
    if os.path.exists(file_path):
        return pd.read_excel(file_path)
    else:
        return pd.DataFrame(columns=["Date of article", "Title", "Subheading", "H2", "H2 Points", "Content", "URL", "Extracted Sentences"])

def save_articles(articles, file_path):
    articles_df = pd.DataFrame(articles)
    articles_df.sort_values(by=["Date of article"], ascending=False, inplace=True)
    articles_df.to_excel(file_path, index=False)

def main():
    logging.info("Starting Gartner articles scraper...")

    # Load existing articles from the file
    existing_articles_df = load_existing_articles(OUTPUT_FILE)
    existing_urls = existing_articles_df["URL"].tolist()

    # Get the latest articles
    new_articles = get_gartner_articles()

    # Process the new articles
    articles_to_add = []
    for article in new_articles:
        if article["URL"] not in existing_urls:
            article_content = get_article_details(article["URL"])
            extracted_sentences = extract_sentences(article_content, KEYWORDS)
            if extracted_sentences:
                article["Extracted Sentences"] = extracted_sentences
                articles_to_add.append(article)

    # Add new articles to the file if any
    if articles_to_add:
        updated_articles_df = pd.concat([existing_articles_df, pd.DataFrame(articles_to_add)], ignore_index=True)
        save_articles(updated_articles_df, OUTPUT_FILE)
        logging.info(f"Added {len(articles_to_add)} new articles to the file.")
    else:
        logging.info("No new articles found related to the specified keywords.")

    logging.info("Scraper finished.")

if __name__ == "__main__":
    main()
