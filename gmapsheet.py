import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

def is_plus_code(text):
    """Determine if the given text is likely a Plus Code."""
    return '+' in text and len(text.split('+')[-1]) >= 3 and len(text.split('+')[0]) >= 3

def authenticate_google_sheets():
    """Authenticate and return the Google Sheets client."""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        print("Successfully authenticated with Google Sheets.")
        return client
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None

def get_sheet(client, workbook_name="Google Map Scraping (Python)", sheet_name="Scraping"):
    """Open the specified workbook and sheet."""
    try:
        workbook = client.open(workbook_name)
    except gspread.SpreadsheetNotFound:
        print(f"Workbook '{workbook_name}' not found.")
        return None
    except Exception as e:
        print(f"Error opening workbook '{workbook_name}': {e}")
        return None

    try:
        sheet = workbook.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        try:
            sheet = workbook.add_worksheet(title=sheet_name, rows="1000", cols="20")
            # Add headers
            sheet.append_row(['Name', 'Phone number', 'Address', 'Plus Code', 'Website'])
            print(f"Created sheet '{sheet_name}' with headers.")
        except Exception as e:
            print(f"Failed to create sheet '{sheet_name}': {e}")
            return None
    except Exception as e:
        print(f"Error accessing sheet '{sheet_name}': {e}")
        return None

    return sheet

def Selenium_extractor(search_query, sheet):
    """Perform web scraping and write data to Google Sheets in bulk."""
    if sheet is None:
        print("No sheet available for writing data.")
        return

    base_url = "https://www.google.com/maps/search/"
    options = webdriver.ChromeOptions()
    # Uncomment the next line to run Chrome in headless mode
    # options.add_argument('--headless')
    try:
        browser = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Failed to initialize Chrome WebDriver: {e}")
        return

    wait = WebDriverWait(browser, 10)
    record = []
    processed_names = set()
    scraped_count = 0

    try:
        # Encode the search query for the URL
        search_query_encoded = urllib.parse.quote_plus(search_query)
        search_url = f"{base_url}{search_query_encoded}/"

        # Navigate to the generated search URL
        browser.get(search_url)
        print(f"Navigating to URL: {search_url}")
        # Wait until the results are loaded
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "hfpxzc")))

        action = ActionChains(browser)

        index = 0
        same_count = 0
        max_same_count = 3

        while True:
            # Fetch the list of elements
            elements = browser.find_elements(By.CLASS_NAME, "hfpxzc")
            current_len = len(elements)
            print(f"Found {current_len} results.")

            if index >= current_len:
                # Scroll to load more results
                try:
                    action.send_keys(u'\ue00F').perform()  # PAGE_DOWN key
                    time.sleep(2)
                    elements = browser.find_elements(By.CLASS_NAME, "hfpxzc")
                    if len(elements) > current_len:
                        same_count = 0
                        print("New elements loaded after scrolling.")
                    else:
                        same_count += 1
                        print(f"No new elements found. same_count: {same_count}")
                        if same_count >= max_same_count:
                            print("No new elements found after scrolling. Ending scraping.")
                            break
                except Exception as e:
                    print(f"Exception during scrolling: {e}")
                    break

            if index >= len(elements):
                print("No more elements to process. Ending scraping.")
                break

            try:
                # Get the name attribute to identify the business
                name = elements[index].get_attribute('aria-label')
                if name in processed_names:
                    print(f"Skipping already processed business: {name}")
                    index += 1
                    continue  # Skip if already processed
                processed_names.add(name)

                # Scroll to the element
                browser.execute_script("arguments[0].scrollIntoView(true);", elements[index])
                time.sleep(1)

                # Get the href attribute of the element
                link = elements[index].get_attribute('href')
                if not link:
                    print(f"No href found for element at index {index}. Skipping.")
                    index += 1
                    continue  # Skip if no href is found

                # Navigate to the business listing
                browser.get(link)
                # Wait until the business name is present
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf.lfPIob")))

                # After navigating to the listing, fetch the page source and parse the business details
                source = browser.page_source
                soup = BeautifulSoup(source, 'html.parser')

                # Extract the business name
                name_html = soup.find('h1', {"class": "DUwDvf lfPIob"})
                if name_html:
                    name = name_html.text.strip()
                else:
                    name = "Not available"

                # Extract all details in "rogA2c" divs
                divs = soup.find_all('div', {"class": "rogA2c"})

                phone = None
                address = None
                plus_code = None
                website = "Not available"

                # Iterate over divs to find phone number, address, plus code, and other details
                for div in divs:
                    div_text = div.get_text(strip=True)

                    if is_plus_code(div_text):
                        plus_code = div_text  # This is the Plus Code
                    elif div_text.startswith("+") or div_text.replace(" ", "").isdigit():
                        phone = div_text  # This is the phone number
                    elif not address:
                        address = div_text  # Assume the first non-plus-code, non-phone is the address

                # Extract the website (if available)
                for div in divs:
                    div_text = div.get_text(strip=True)
                    if div_text.startswith('http') or '.' in div_text:
                        website = div_text
                        break

                # Append the business details to the record list
                record.append([name, phone, address, plus_code, website])
                scraped_count += 1  # Increment the scraped contacts count

                # Print the scraped data
                print(f"{name}, {phone}, {address}, {plus_code}, {website}")

                # Navigate back to the search results page
                browser.back()
                # Wait until the search results are loaded
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "hfpxzc")))

                index += 1  # Move to the next index

            except Exception as e:
                print(f"An error occurred while processing element {index}: {e}")
                # Attempt to navigate back to the search results page in case of error
                try:
                    browser.back()
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "hfpxzc")))
                except Exception as nav_e:
                    print(f"Failed to navigate back after error: {nav_e}")
                index += 1
                continue

    finally:
        # Write all collected data to Google Sheets in bulk
        if record:
            try:
                sheet.append_rows(record, value_input_option='RAW')
                print("Data written to Google Sheets successfully.")
            except Exception as e:
                print(f"Failed to write data to Google Sheets: {e}")
        else:
            print("No data scraped.")

        # Close the browser
        browser.quit()

        # Notify the user that scraping is finished
        print("Finished Scraping and data written to Google Sheets.")

def main():
    # Prompt the user for a search query
    search_query = input("Enter your Google Maps search query: ").strip()
    if not search_query:
        print("No search query provided. Exiting.")
        return

    # Authenticate and get the Google Sheets client
    client = authenticate_google_sheets()
    if client is None:
        print("Authentication failed. Exiting.")
        return

    # Get the Google Sheet
    sheet = get_sheet(client, "Google Map Scraping (Python)", "Scraping")
    if sheet is None:
        print("Failed to access the Google Sheet. Exiting.")
        return

    # Start scraping
    Selenium_extractor(search_query, sheet)

if __name__ == "__main__":
    main()
