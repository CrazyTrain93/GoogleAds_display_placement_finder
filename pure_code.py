# Import the needed libraries
import pandas as pd
import requests
import gspread
from google.oauth2 import service_account

# look up the requirements.txt if you need to pip install sth

# Read API key and search engine ID from config.txt - rename this if you store it somewhere else
# Here you need a Programmable Search Engine Account from Google and Set up your Programmable Search Engine + API to get the API key + Engine ID from your Google Cloud Account
# Here you can Enable the Programmable Search Engine: https://programmablesearchengine.google.com/  

# open my config.txt where i stored API Key and Search Engine ID - its in gitignore u need ur own
with open('config.txt', 'r') as file:
    lines = file.readlines()

# read the api key in which is in the first line (idx 0)
api_key = lines[0].strip().split('=')[1]
# do the same for search_engine_id in line 2 (idx 1)
search_engine_id = lines[1].strip().split('=')[1]

# Fetch the First 30 Results for Each of the 30 Keywords
# The Google Cloud CustomSearchAPI has only 100 free quota limits per day, 
# we call each Keyword 3 times for Position 1-30, 
# i would not recommend to use more than 30 keywords, if you have no paid version of google cloud!!!

# Assuming we want to Place our Display Ad Campaigns around E-Mobility Target Groups
keywords = [
    "Elektromobilität", "Elektrofahrrad", "Elektrofahrzeug",
    "E-Auto", "Elektroantrieb", "E-Bike Ladeinfrastruktur",
    "Elektro-Ladestation", "Batterietechnologie", "E-Mobilität Nachrichten",
    "Elektroauto Hersteller", "E-Roller Modelle", "Elektroauto Test",
    "Elektroauto Reichweite", "Elektroauto Preis", 
    "Elektroauto Förderung", "E-Bike Markt", "Elektroauto Vergleich",
    "E-Bike Test", "Elektroauto Akku", "Elektroauto Ladetechnik",
    "Elektroauto Infrastruktur", "Elektroauto Umwelt", "E-Bike Zukunft",
    "Elektroauto Wartung",
    "Elektroauto Laden",
    "E-Bike Sicherheit", "Elektroauto Testberichte", "Elektroauto Reichweitenangst",
    "E-Bike Förderprogramme", "Elektroauto Steuervorteile"
]

# I used this 2 Keywords while development to verify my results
# keywords = ["Elektroauto Reichweitenangst","Elektrofahrrad"]

# Define the Google Custom Search API URL Function
# Here you can read what parameters u can use i will explain the ones i used
# https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list?hl=de&apix_params=%7B%22num%22%3A30%2C%22start%22%3A1%7D


def get_search_results(api_key, search_engine_id, query, start):
    """
     key = your API Key
     cx = your Search Engine ID
     q = search query or your keywords
     start = at which position of google search u want to start thats why we iterate over it
     num = num 10 is maximum, there are only 10 entries per google search site
     hl=de  = this parameter sets the interface language of the search engine
     cr=countryDE = restricts the search results to pages from a specific country
     lr=lang_de = restricts results to pages written in specific language
    """

    # define our customsearch url 
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={search_engine_id}&q={query}&start={start}&num=10&hl=de&cr=countryDE&lr=lang_de"
   # try catch block for timedout pages or other errors to prevent script from crashing
    try:
        # set the timeout to 5 large pages could take a bit to respond
        r = requests.get(url, allow_redirects=False, timeout=5) 
        if r.status_code == 200:
            return r.json() # read in the json content when status code was 200
        else:
            print(f"Error {r.status_code}: {r.text}") # otherwise print error message
            return None
    except requests.Timeout: # specific errors i try to catch to know more about them
        print("Request timed out")
        return None
    except requests.RequestException as e: # other errors
        print(f"An error occured: {e}")
        return None
    
# create a list which holds all results at the end
all_results = []

# iterate over all provided keywords
for keyword in keywords:
    for start in range(1,31,10): # Start from 1 and go up by 10 till 30, bc each Google Page has 10 entries (we scrape the first 3 Sites)
        response = get_search_results(api_key, search_engine_id, keyword, start) # call our defined function for each keyword 3 times
        if response:
            for item in response.get("items", []): # if response = true get items of the json
                item["keyword"] = keyword # Add the used Keyword for later (Analytics Part)
            all_results.extend(response.get("items", [])) # hang on each iteration to the dictionary


# here i need to calculate the position on which article was found for each keyword
current_keyword = ""
data = []

# if keyword changes after 30 position per keyword reset index to position 1 (the google ranking of the site)
for idx, result in enumerate(all_results, 1):
    if result['keyword'] != current_keyword:
        idx = 1  # Reset the index to 1 for the new keyword
        current_keyword = result['keyword']
    # make sure index or our Google Position iterates from 1-30 for each word
    data.append([(idx-1) % 30 + 1,  result['title'], result["snippet"], result["displayLink"], result['keyword'], result['link']]) # append everything we need for 1 Dataframe

# Create a DataFrame
df = pd.DataFrame(data, columns=["Position", "Title", "Snippet", "displayLink", "Keyword", "Link", ])

# define a valid header which mimics a real User, to make sure not to get 404 or other responses from bot detection on the websites
headers_http = {"User-Agent" : "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:99.0) Gecko/20100101 Firefox/99.0"}

# Iterate over all display Links add /ads.txt to them (this indicates who and if websites do advertisement)
# when getting a 200 response from them we will add the Link to the ads.txt File in the new Column otherwise "No Advertisement"

# iterate over our Dataframe for each finding with customsearch API
for idx, row in df.iterrows():
    # build our /ads.txt url Example: https://www.bild.de/ads.txt
    url = "https://"+row["displayLink"]+ "/ads.txt"
# request every ads txt and forbid to Redirect! We want only Pages with working /ads.txt directories on their page
    # /ads.txt is always stored in the root directory so it is easy accessible for crawlers
    try:
        response = requests.get(url, headers=headers_http, allow_redirects=False, timeout=5) # no redirects and timeout 5 for slower sites

        if response.status_code == 200:
            df.at[idx, "AdvertisementLink"] = url # if we find a ads.txt we add the link to our df
        
        else:
            df.at[idx, "AdvertisementLink"] = "No Advertisement possible" # otherwise entry for no advertisement (mostly business websites or institutional, government websites who do not advertise)

# catch possible exceptions during the process (we scrape over nearly 900 urls here)
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        df.at[idx, "AdvertisementLink"] = "No Advertisement possible" # For Exceptions we assume the sites dont Advertise

# Here we prepare Sheet 2 of our 2 Sheeted Google Sheets Document
# Filter out rows where AdvertisementLink is "No Advertisement"
filtered_df = df[df['AdvertisementLink'] != "No Advertisement possible"]

# Calculate average position and group by AdvertisementLink, displayLink, and Keyword
# here we compress the df and take the Position Mean for each Site if it has more Placements per Keyword in top 30
result_df = filtered_df.groupby(['AdvertisementLink', 'displayLink', 'Keyword']).agg(
    AveragePosition=('Position', 'mean')
).reset_index()

# Create a DataFrame with distinct AdvertisementLink, displayLink, and Keyword and Drop Duplicate rows
distinct_df = result_df.drop_duplicates(subset=['AdvertisementLink', 'displayLink', 'Keyword'])

# we dont need the displayLink in both sheets
df.drop("displayLink", axis=1, inplace=True)

# Drop the index column
df = df.reset_index(drop=True)
distinct_df = distinct_df.reset_index(drop=True)

# Define the scope for googleapis
scope = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

# Here you need your Google Cloud Project Set up and Download your json Credentials
# https://cloud.google.com/
# Insert your Google API JSON File here! Replace my old one (and add it to your Project Folder)
path = "displayadsplacem-1711913302419-44b8d45015ee.json" 

# Authenticate using credentials
credentials = service_account.Credentials.from_service_account_file(path, scopes=scope)
client = gspread.authorize(credentials)

# Open the Google Sheet - Provide the Name of your Sheet
sheet = client.open('Display_Marketing_Placement_finder')

# Clear the 2 Sheets
sheet.worksheet("Ads Placement").clear()
sheet.worksheet("Detailed Data").clear()


# Write DataFrame to Google Sheet
# Insert the headers
headers_ads = distinct_df.columns.tolist()
sheet.worksheet('Ads Placement').insert_row(headers_ads, 1)

headers_distinct = df.columns.tolist()
sheet.worksheet('Detailed Data').insert_row(headers_distinct, 1)

# Insert the data
gspread_dataframe = distinct_df.values.tolist()
sheet.worksheet('Ads Placement').insert_rows(gspread_dataframe, 2) # 2 specifies which sheet

# same for other table inside the same google sheet
gspread_dataframe_distinct = df.values.tolist()
sheet.worksheet('Detailed Data').insert_rows(gspread_dataframe_distinct, 2)
