import yfinance as yf
import pandas as pd
from openpyxl import load_workbook
from datetime import datetime

# Define the file path
file_path = r'C:\Code\MachineLearning\StockRevenue\stock_revenue_statistics.xlsx'

# Load the workbook and read the 'ID' sheet
workbook = load_workbook(file_path)
sheet = workbook['ID']  # Replace 'ID' with the correct sheet name if it's different
data = list(sheet.values)
cols = next(iter(data))  # Read the header row
stock_list = pd.DataFrame(data[1:], columns=cols)  # Skip the header

# Create an empty DataFrame to store dividend data
dividend_data = pd.DataFrame()

# Fetch dividend data for the years 2020-2023
current_year = datetime.now().year
years = range(2020, current_year + 1)

# Use the entire stock list instead of limiting to the first 10
for i in stock_list.index:
    stock_id = stock_list.loc[i, 'CompanyCode'] + '.TW'
    ticker = yf.Ticker(stock_id)
    
    # Fetch dividend data
    dividends = ticker.dividends
    dividends = dividends[dividends.index.year.isin(years)]  # Filter dividends for 2020-2023
    dividends = dividends.groupby(dividends.index.year).sum()  # Sum dividends by year
    
    # Create a DataFrame for the current stock with dividends per year
    stock_dividends = pd.DataFrame({
        'stock_id': stock_list.loc[i, 'CompanyCode'],
        'company_name': stock_list.loc[i, 'CompanyName'],
    }, index=[0])
    
    # Add dividend data to the DataFrame
    for year in years:
        stock_dividends[f'{year}dividend'] = dividends.get(year, 0)
    
    # Append to the main dividend DataFrame
    dividend_data = pd.concat([dividend_data, stock_dividends], ignore_index=True)

# Save the dividend data to the 'dividend' sheet in the existing workbook
with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
    dividend_data.to_excel(writer, sheet_name='dividend', index=False)

print(f"Dividend data saved to {file_path} in the 'dividend' sheet.")
