import pandas as pd
import requests
import os
import time
import openpyxl
from datetime import datetime, timedelta

def get_monthly_revenue(year_month):
    print(f"Start to crawl {year_month}...")
    url = f'https://mops.twse.com.tw/nas/t21/sii/t21sc03_{year_month}_0.html'

    folder_name = "StockRevenue"
    os.makedirs(folder_name, exist_ok=True)  # Create folder if it doesn't exist

    success = False
    attempts = 0
    while not success and attempts < 5:
        try:
            res = requests.get(url)
            res.encoding = 'big5'

            if res.status_code == 200:
                html_df = pd.read_html(res.text)
                df = pd.concat([df for df in html_df if df.shape[1] == 11])
                df.columns = df.columns.get_level_values(1)
                
                file_name = os.path.join(folder_name, f"stock_raw_{year_month}.xlsx")
                df.to_excel(file_name, index=False)
                print(f"Data for {year_month} saved to {file_name}")
                success = True
            else:
                raise Exception("Failed to fetch data")

        except Exception as e:
            print(f"Error occurred: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            attempts += 1

    if not success:
        print(f"Failed to fetch data for {year_month} after {attempts} attempts.")

def calculate_dates():
    today = datetime.today()

    # Adjust the year and month for the URL format (year - 1911)
    latest_year = today.year - 1911
    latest_month = today.month

    # If today is before the 11th, go back one additional month
    if today.day < 11:
        latest_month -= 1

    # Adjust for year rollover
    if latest_month <= 0:
        latest_year -= 1
        latest_month += 12

    monthly_dates = []

    for i in range(1,14):
        year = latest_year
        month = latest_month - i
        if month <= 0:
            month += 12
            year -= 1
        monthly_dates.append(f"{year}_{month}")

    return monthly_dates[::-1]  # Chronological order

def consolidate_data(monthly_dates, folder_name='StockRevenue'):
    all_data = {}

    for date in monthly_dates:
        file_name = os.path.join(folder_name, f"stock_raw_{date}.xlsx")
        print(f"Processing file: {file_name}")

        if os.path.exists(file_name):
            workbook = openpyxl.load_workbook(file_name)
            sheet = workbook.active

            for row in sheet.iter_rows(min_row=2, values_only=True):
                company_code = row[0]
                company_name = row[1]
                revenue = row[2]

                # Skip the row if the company name is '合計'
                if company_name == '合計':
                    continue

                if company_code not in all_data:
                    all_data[company_code] = {'CompanyName': company_name, f'{date}_Revenue': revenue}
                else:
                    all_data[company_code][f'{date}'] = revenue

        else:
            print(f"File not found: {file_name}")
            continue

    # Write combined data to a new Excel file
    write_combined_data_to_excel(all_data)

def write_combined_data_to_excel(data):
    
    file_name = os.path.join('StockRevenue', f"stock_revenue_statistics.xlsx")
    # Check if the file exists
    if os.path.exists(file_name):
        print(f"The file '{file_name}' exists.")
    else:
        print(f"The file '{file_name}' does not exist.")

    workbook = openpyxl.load_workbook(file_name)
    revenue_sheet = workbook["Revenue"]

    # Clear existing data (excluding the header row if it exists)
    revenue_sheet.delete_rows(1, revenue_sheet.max_row + 1)

    # Writing the header
    headers = ['CompanyCode', 'CompanyName'] + [f'{date}_Revenue' for date in monthly_dates]
    revenue_sheet.append(headers)

    # Writing the new data
    for company_code, info in data.items():
        row = [company_code, info['CompanyName']] + [info.get(f'{date}_Revenue', '') for date in monthly_dates]
        print("Appending row:", row)  # Debug print
        revenue_sheet.append(row)
    print(revenue_sheet)
    workbook.save(file_name)
    print(f"Data saved to {file_name}")

if __name__ == '__main__':

    monthly_dates = calculate_dates()
    print(monthly_dates)

    # Crawl and save data for each month
    #for date in monthly_dates:
    #    get_monthly_revenue(date)

    consolidated_data = consolidate_data(monthly_dates)
    print("Consolidated data saved to 'stock_revenue_statistics.xlsx'")
