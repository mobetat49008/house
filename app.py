import shioaji as sj
import pandas as pd
import json
import pandas as pd
import requests
import math
import os
import datetime

from datetime import datetime, timedelta
from io import StringIO
from flask import Flask,render_template, jsonify
from Sinopac_Futures import list_accounts,list_position,get_stock_balance,list_margin

# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file
app = Flask(__name__)

# Global variable for the API
api = None

def get_appropriate_date():
    """Determines the correct date based on the current time."""
    now = datetime.now()
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        return (now - timedelta(days=1)).strftime('%Y%m%d')
    else:
        return now.strftime('%Y%m%d')

# Example function to replace NaN values
def replace_nan(val):
    if isinstance(val, float) and math.isnan(val):
        return None  # or return "" if you prefer an empty string
    return val
    
def get_dividend_data(excel_file_path):
    try:
        # Read the 'dividend' sheet
        dividend_df = pd.read_excel(excel_file_path, sheet_name='dividend')
        # Creating a dictionary for quick access to dividend data based on stock_id
        dividend_dict = {str(key): value for key, value in dividend_df.set_index('stock_id')['2023dividend'].items()}

        return dividend_dict
    except Exception as e:
        print(f"Error reading dividend data: {e}")
        return {}

def get_revenue_data(excel_file_path):
    try:
        # Read the 'Revenue' sheet
        revenue_df = pd.read_excel(excel_file_path, sheet_name='Revenue')
        
        # Create a dictionary to hold the revenue data
        revenue_dict = {}
        
        # Iterate over each row in the DataFrame to build a dictionary for each company
        for index, row in revenue_df.iterrows():
            company_code = str(row['CompanyCode'])
            revenue_data = row.filter(like='_Revenue').to_dict()
            revenue_dict[company_code] = revenue_data

        #print(f"WEIII---{revenue_dict}")
        return revenue_dict
    except Exception as e:
        print(f"Error reading revenue data: {e}")
        return {}

def calculate_mom_yoy(revenue_dict):
    results = {}
    
    for company_code, revenues in revenue_dict.items():
        # Sort the keys to find the latest month (which should be the rightmost column)
        sorted_keys = sorted(revenues.keys(), key=lambda x: [int(i) for i in x.split('_')[:2]])
        latest_month_key = sorted_keys[-1]  # The latest month key

        # Extract year and month from the key
        latest_year, latest_month = map(int, latest_month_key.split('_')[:2])
        
        # Calculate the keys for the same month last year and the last month
        last_year_key = f"{latest_year - 1}_{latest_month:02d}_Revenue"
        last_month = latest_month - 1 if latest_month > 1 else 12
        last_month_year = latest_year if latest_month > 1 else latest_year - 1
        last_month_key = f"{latest_year}_{last_month}_Revenue" if last_month >= 10 else f"{latest_year}_{last_month}_Revenue"

        # Retrieve the revenue for the latest month, the previous month, and the same month of the previous year
        latest_revenue = revenues.get(latest_month_key, 0)
        last_month_revenue = revenues.get(last_month_key, 0)
        last_year_revenue = revenues.get(last_year_key, 0)
        
        # Calculate MoM and YoY, handling cases where revenue for the previous period is zero or missing
        mom = ((latest_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue else None
        yoy = ((latest_revenue - last_year_revenue) / last_year_revenue * 100) if last_year_revenue else None
        
        # Format MoM and YoY as percentages with two decimal places
        mom_formatted = f"{mom:.2f}%" if mom is not None else None
        yoy_formatted = f"{yoy:.2f}%" if yoy is not None else None

        # Store the formatted MoM and YoY in the results dictionary
        results[company_code] = {
            'MoM': mom_formatted,
            'YoY': yoy_formatted
        }

    return results

def fetch_data(url, date):
    """Fetches data from the specified URL for the given date."""
    try:
        response = requests.get(url.format(date), timeout=30)
        response.raise_for_status()
        return pd.read_html(response.text)
    except requests.exceptions.Timeout:
        return "N/A - Timeout occurred"
    except requests.exceptions.HTTPError as e:
        return f"N/A - HTTP Error: {e}"
    except Exception as e:
        return f"N/A - An error occurred: {e}"

def format_dataframe(df):
    """Formats the DataFrame, adjusting numerical values."""
    df.columns = df.columns.droplevel()
    for col in df.columns[1:]:
        df[col] = (df[col] / 100000000).round(2)
    return df

@app.route('/financial_data')
def financial_data():
    date_to_use = get_appropriate_date()
    raw_data = fetch_data("http://www.twse.com.tw/fund/BFI82U?response=html&dayDate={0}", date_to_use)
    print("WEIIIIIIIIIIIIIIIIIIIIIIIIIIIIII")
    if isinstance(raw_data, list) and len(raw_data) > 0:
        formatted_df = format_dataframe(raw_data[0])
        #return formatted_df.to_json(orient='records')
        return render_template('main.html', date_to_use=date_to_use, formatted_data=formatted_df.to_json(orient='records'))
    else:
        return jsonify({"error": str(raw_data)})

@app.route('/stock_data')
def stock_data():
    global api
    data = []
    revenue = {}

    # Get the current directory where the Python script is located
    current_directory = os.path.dirname(__file__)

    # Construct the relative path to the Excel file
    excel_file_path = os.path.join(current_directory, 'StockRevenue', 'stock_revenue_statistics.xlsx')
    
    if api:
        usage = api.usage()
        print(f"connection:{usage.connections},remaining_bytes:{usage.remaining_bytes}")
        
        df_positions = list_position(api, "Stock")
        df_json = pd.read_json('stock_number.json', orient='records', lines=True)
        code_to_name = {str(key): value for key, value in zip(df_json[2], df_json[3])}
        
        df_positions['code'] = df_positions['code'].astype(str)
        df_positions['Chinese Name'] = df_positions['code'].map(code_to_name)

        # Calculate 'Profit Percentage' as float for sorting
        df_positions['Profit Percentage'] = df_positions.apply(
            lambda row: (row['last_price'] - row['price']) / row['price'] * 100 if row['price'] != 0 else None,
            axis=1
        )

        total_price = int((df_positions['price'] * df_positions['quantity']).sum() * 1000)
        total_last_price = int((df_positions['last_price'] * df_positions['quantity']).sum() * 1000)
        total_pnl = df_positions['pnl'].sum()

        # Calculate 'Stock Percentage' as float for sorting
        df_positions['Stock Percentage'] = df_positions['price'] * df_positions['quantity'] * 1000 / total_price * 100

        # Sort and get top 10 for 'Profit Percentage' and 'Stock Percentage'
        top_profit = df_positions.nlargest(10, 'pnl')[['Chinese Name', 'pnl']]
        top_stock = df_positions.nlargest(10, 'Stock Percentage')[['Chinese Name', 'Stock Percentage']]

        # Convert back to string format with '%' for display
        #top_profit['Profit Percentage'] = top_profit['Profit Percentage'].apply(lambda x: f'{x:.2f}%')
        top_stock['Stock Percentage'] = top_stock['Stock Percentage'].apply(lambda x: f'{x:.2f}%')

        data = df_positions.to_dict(orient='records')
        balance = get_stock_balance(api)
        accountBalance = balance.acc_balance

        dividend_dict = get_dividend_data(excel_file_path)
        revenue_dict = get_revenue_data(excel_file_path)
        revenue = calculate_mom_yoy(revenue_dict)
        for position in data:
            
            for key, value in position.items():
                position[key] = replace_nan(value)

            stock_code = str(position['code'])
            position['2023dividend'] = dividend_dict.get(stock_code, 'N/A')
            try:
                position['2023MoM'] = revenue[stock_code]['MoM']
                position['2023YoY'] = revenue[stock_code]['YoY']
            except:
                position['2023MoM'] = "N/A"
                position['2023YoY'] = "N/A"
            price_per_share = position.get('last_price', 1)  # Ensure this is the correct field for the share price
            # Calculate Dividend Yield and handle cases where price_per_share is 0
            if position['2023dividend'] != 'N/A':
                try:
                    # Convert dividend to a float for calculation
                    dividend = float(position['2023dividend'])
                    dividend_yield = (dividend / price_per_share) * 100 if price_per_share != 0 else 0
                    position['Dividend Yield'] = round(dividend_yield, 2)  
                except ValueError:
                    print(f"Error in converting dividend: {position['2023dividend']}")
                    position['Dividend Yield'] = 'Error'
            else:
                position['Dividend Yield'] = 'N/A'

        # Convert the 'pnl' column from DataFrame to a list
        pnl_data = df_positions['pnl'].tolist()
        # Package everything into a dictionary to be returned as JSON
        response_data = {
            "positions": data,
            "total_price": total_price,
            "total_last_price": total_last_price,
            "total_pnl": total_pnl,
            "accountBalance": accountBalance,
            "top_profit_data": top_profit.to_dict(orient='records'),
            "top_stock_data": top_stock.to_dict(orient='records'),
            "pnl_data": pnl_data  # Add PnL data here
        }
        return jsonify(response_data)

    else:
        # Handle the case where 'api' is not available
        return jsonify({"error": "API not available"}), 500

@app.route('/futures_data')
def futures_data():
    global api

    if api:
        usage = api.usage()
        print(f"connection:{usage.connections},remaining_bytes:{usage.remaining_bytes}")
        try:
            total_pnl = list_margin(api).equity
            df_positions = list_position(api, "Futures")
            if df_positions.empty:
                print("No futures data available.")

            # Additional calculations as required
            data = df_positions.to_dict(orient='records')

            print(total_pnl)
            response_data = {
                "positions": data,
                "total_pnl": total_pnl,
            }
            return jsonify(response_data)

        except Exception as e:
            print("Error in /futures_data:", e)
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "API not available"}), 500

@app.route('/')
def main():
    global api
    data = []
    date_to_use = get_appropriate_date()
    if api:
        # Fetch and process the new data
        url = "http://www.twse.com.tw/fund/BFI82U?response=html&dayDate={0}"
        date_to_use = get_appropriate_date()
        raw_data = fetch_data(url, date_to_use)

        financial_data_html = ""
        if isinstance(raw_data, list) and len(raw_data) > 0:
            formatted_df = format_dataframe(raw_data[0])
            financial_data_html = formatted_df.to_html(classes='w3-table w3-striped w3-white')
        else:
            financial_data_html = "<p>Error fetching financial data: " + str(raw_data) + "</p>"
        # Get the DataFrame from list_position
        df_positions = list_position(api,"Stock")

        # Read the JSON file into a DataFrame
        df_json = pd.read_json('stock_number.json', orient='records', lines=True)

        # Convert keys in the dictionary to strings
        code_to_name = {str(key): value for key, value in zip(df_json[2], df_json[3])}
        # Assuming 'code' column in df_positions is a string, convert it to integer for proper mapping
        df_positions['code'] = df_positions['code'].astype(str)

        # Map the code to Chinese names, insert a new column
        df_positions['Chinese Name'] = df_positions['code'].map(code_to_name)
        
        # Calculate Profit Percentage, format it to two decimal places with a '%' sign, or handle zero division
        df_positions['Profit Percentage'] = df_positions.apply(
            lambda row: "{:.2f}%".format((row['last_price'] - row['price']) / row['price'] * 100) 
                        if row['price'] != 0 else 'N/A',
            axis=1
        )

        # Calculate the sum of 'price', 'last_price', and 'pnl'
        total_price = int((df_positions['price']*df_positions['quantity']).sum() * 1000)
        total_last_price = int((df_positions['last_price']*df_positions['quantity']).sum() * 1000)
        total_pnl = df_positions['pnl'].sum()

        # Calculate the percentage of total price for each stock. The reason to * 1000 is because total price has *1000.
        df_positions['Stock Percentage'] = (df_positions['price'] * df_positions['quantity'] * 1000/ total_price * 100).apply(lambda x: "{:.2f}%".format(x))

        # Convert DataFrame to list of dicts for Jinja2 rendering
        data = df_positions.to_dict(orient='records')

        balance = get_stock_balance(api)
        accountBalance = balance.acc_balance

    return render_template('main.html', positions=data, total_price=total_price, total_last_price=total_last_price, total_pnl=total_pnl,accountBalance=accountBalance,financial_data_html=financial_data_html, date_to_use=date_to_use)

if __name__ == '__main__':

    # Reading the JSON file
    with open(configuration_file_path, 'r') as file:
        data = json.load(file)

    # Accessing the fields from the JSON data
    person_id_json = data['PersonID']
    password = data['Password']
    ca_path_json = data['ca_path']
    API_KEY = data['API_KEY']
    API_SECRET_KEY = data['API_SECRET_KEY']

    #First time need to add simulation=True for confirmation
    api = sj.Shioaji()
    api.login(
        api_key=API_KEY, 
        secret_key=API_SECRET_KEY, 
        contracts_cb=lambda security_type: print(f"{repr(security_type)} fetch done.")
    )

    result = api.activate_ca(
        ca_path=ca_path_json,
        ca_passwd=password,
        person_id=person_id_json,
    )
    
    if not result:
        print(f"The CA status is {result}")

    '''
    ################This section is to download the stock code################
    result = requests.get("https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=4&issuetype=R&industry_code=&Page=1&chklike=Y")
    # Assuming the DataFrame is the first table in the HTML
    df_full = pd.read_html(result.text)[0]

    # Select the 2nd and 3rd columns (3rd and 4th if counting from 1)
    df_selected = df_full.iloc[1:, [2, 3]]  # 1: to skip the first row, [2, 3] to select columns
    df_selected.to_json('stock_number.json', orient='records', lines=True)
    ##########################################################################
    '''
    # Run the application on all network interfaces, not just the loopback interface
    app.run(host='0.0.0.0', port=5000,debug=True)