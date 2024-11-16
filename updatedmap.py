import tkinter as tk
from tkinter import messagebox
import threading
from selenium import webdriver
from bs4 import BeautifulSoup
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
import urllib.parse  # For URL encoding
import os  # For locating the Documents folder

def is_plus_code(text):
    """Function to determine if a given text is likely a Plus Code."""
    return '+' in text and len(text.split('+')[-1]) >= 3 and len(text.split('+')[0]) >= 3

def Selenium_extractor(search_query, download_path, status_label, scraped_label):
    """Function to perform the web scraping."""
    base_url = "https://www.google.com/maps/search/"
    browser = webdriver.Chrome()
    record = []
    processed_names = set()  # Track already processed businesses
    scraped_count = 0  # Initialize scraped contacts count

    # Encode the search query for the URL
    search_query_encoded = urllib.parse.quote_plus(search_query)
    search_url = f"{base_url}{search_query_encoded}/"
    
    # Navigate to the generated search URL
    browser.get(search_url)
    time.sleep(5)
    
    action = ActionChains(browser)

    prev_len = 0
    same_count = 0
    max_same_count = 3  # Max times to detect no new elements before stopping

    while True:
        status_label.config(text="Scraping in progress...")  # Update status in the GUI

        # Fetch the list of elements
        a = browser.find_elements(By.CLASS_NAME, "hfpxzc")

        current_len = len(a)
        print(f"Found {current_len} results.")

        if current_len > prev_len:
            same_count = 0  # Reset counter if new elements are found
        else:
            same_count += 1
            if same_count >= max_same_count:
                print("No new elements found after scrolling. Ending scraping.")
                break  # Exit the loop if no new elements are found after several attempts

        prev_len = current_len

        for i in range(current_len):
            try:
                # Get the name attribute to identify the business
                name = a[i].get_attribute('aria-label')
                if name in processed_names:
                    continue  # Skip if already processed
                processed_names.add(name)

                # Scroll to the element
                browser.execute_script("arguments[0].scrollIntoView(true);", a[i])
                time.sleep(1)

                # Open each business listing in a new tab with Ctrl + Click
                action.key_down(u'\ue009').click(a[i]).key_up(u'\ue009').perform()  # Ctrl + Click
                time.sleep(2)

                # Switch to the new tab
                browser.switch_to.window(browser.window_handles[-1])
                time.sleep(2)

                # After switching to the new tab, fetch the page source and parse the business details
                source = browser.page_source
                soup = BeautifulSoup(source, 'html.parser')

                # Extract the business name
                Name_Html = soup.findAll('h1', {"class": "DUwDvf lfPIob"})
                if Name_Html:
                    name = Name_Html[0].text

                # Extract all details in "rogA2c" divs
                divs = soup.findAll('div', {"class": "rogA2c"})

                phone = None
                address = None
                plus_code = None
                website = "Not available"

                # Iterate over divs to find phone number, address, plus code, and other details
                for div in divs:
                    div_text = div.text.strip()

                    if is_plus_code(div_text):
                        plus_code = div_text  # This is the Plus Code
                    elif div_text.startswith("+") or div_text.replace(" ", "").isdigit():
                        phone = div_text  # This is the phone number
                    elif not address:  # Assume the first non-plus-code, non-phone is the address
                        address = div_text

                # Extract the website (if available)
                for z in range(len(divs)):
                    div_text = divs[z].text.strip()
                    if div_text.startswith('http') or '.' in div_text:
                        website = div_text
                        break

                # Print the extracted information
                print([name, phone, address, plus_code, website])

                # Append the business details to the record list
                record.append((name, phone, address, plus_code, website))
                scraped_count += 1  # Increment the scraped contacts count

                # Update the scraped_label in the GUI
                scraped_label.after(0, lambda count=scraped_count: scraped_label.config(text=f"Scraped {count} contacts"))

                # Save the DataFrame to a CSV file in the Documents folder
                save_path = f"{download_path}/{search_query}_results.csv"
                df = pd.DataFrame(record, columns=['Name', 'Phone number', 'Address', 'Plus Code', 'Website'])
                df.to_csv(save_path, index=False, encoding='utf-8')

                # Close the new tab and switch back to the original tab
                browser.close()
                browser.switch_to.window(browser.window_handles[0])

            except Exception as e:
                print(f"An error occurred while processing element {i}: {e}")
                # Close any extra tabs if open
                if len(browser.window_handles) > 1:
                    browser.close()
                    browser.switch_to.window(browser.window_handles[0])
                continue

        # Scroll to load more results
        try:
            # Scroll down by sending PAGE_DOWN key
            action.send_keys(u'\ue00f').perform()  # PAGE_DOWN key
            time.sleep(2)
        except Exception as e:
            print(f"Exception during scrolling: {e}")
            break

    status_label.config(text="Scraping completed!")  # Update the GUI when scraping is done
    browser.quit()
    
    # --- Alert when scraping is finished ---
    messagebox.showinfo("Finished Scraping", "Finished Scraping")

# --- GUI Code ---

def start_scraping():
    """Start the scraping process in a separate thread."""
    search_query = entry_query.get().strip()  # Get the user's search query

    if search_query:
        status_label.config(text="Starting scraping...")
        scraped_label.config(text="Scraped 0 contacts")  # Reset scraped contacts count
        # Automatically save to the Documents folder
        documents_path = os.path.join(os.path.expanduser("~"), "Documents")  # Get the Documents folder path
        threading.Thread(target=Selenium_extractor, args=(search_query, documents_path, status_label, scraped_label)).start()
    else:
        messagebox.showwarning("Input Required", "Please enter a search query.")

def on_closing():
    """Terminate the scraping process and close the window."""
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        root.destroy()  # Close the Tkinter window and terminate the app

# Initialize the Tkinter GUI
root = tk.Tk()
root.title("Google Map Scraper")

# Adjust the window layout
root.geometry("300x250")  # Increased height to accommodate the new label

# Create input label and entry for the search query
label_query = tk.Label(root, text="Search Google Maps")
label_query.pack(pady=10)

entry_query = tk.Entry(root, width=40)  # Made the input field wider
entry_query.pack(pady=10)

# Create a button to start the scraping process
button_start = tk.Button(root, text="Start Scraping", command=start_scraping)
button_start.pack(pady=10)

# Create a label to display status updates
status_label = tk.Label(root, text="Waiting for input...", fg="green")
status_label.pack(pady=10)

# Create a label to display the number of scraped contacts
scraped_label = tk.Label(root, text="Scraped 0 contacts", fg="blue")
scraped_label.pack(pady=5)

# Bind the window close button to trigger the termination
root.protocol("WM_DELETE_WINDOW", on_closing)

# Run the GUI event loop
root.mainloop()
