import shioaji as sj
import pandas as pd
import json
import pandas as pd
import requests
import math
import os
import datetime
import time
import threading
import redis
import re

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from OP_OI import get_today_date,calculate_week_of_month,extract_call_oi,extract_put_oi,plot_call_put_oi,calculate_wednesday_of_week,load_df,get_filename
from io import StringIO
from flask import Flask,render_template, jsonify,request,redirect, url_for, session, flash
from Sinopac_Futures import list_accounts,list_position,get_stock_balance,list_margin
from collections import defaultdict, deque
from shioaji import TickFOPv1, Exchange
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from collections import OrderedDict

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file
app = Flask(__name__)
app.secret_key = '123'
CORS(app)  # You might need to specify parameters based on your security needs
socketio = SocketIO(app, logger=True, engineio_logger=True, cors_allowed_origins="*")

# Global variable for the API
api = None
counter =0

line_bot_api = LineBotApi('VHc381SO8ZVskAIWrcwr359MwdqQddLblA4R566bkF8wUVfdxf13dOa/eE5fk21I9DBZ1idtIDpty1b5PeeG4iQdk2aKeMprFaxn+TCyzNbPwRa8JwlPM/FftAfc9SOB10YEjRyDxJgM2DpbtRknFAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('949ccb6111446334ec84f1dfba44ca2c')

url = 'https://notify-api.line.me/api/notify'
token = 'JGq9Hk4A6wIECngAAkSZj7KhAYqiu0ChaAbDYwwvdFv'
headers = {
    'Authorization': 'Bearer ' + token    # 設定權杖
}

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# redis setting
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

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

def fetch_data(url, date_str):
    max_retries = 10  # Adjust this number as needed
    retry_count = 0

    # Convert date string to datetime object
    date = datetime.strptime(date_str, "%Y%m%d")

    while retry_count < max_retries:
        try:
            formatted_date = date.strftime("%Y%m%d")
            print(formatted_date)
            response = requests.get(url.format(formatted_date), timeout=30)
            response.raise_for_status()
            return pd.read_html(response.text),formatted_date
        except requests.exceptions.Timeout:
            return "N/A - Timeout occurred"
        except requests.exceptions.HTTPError as e:
            return f"N/A - HTTP Error: {e}"
        except Exception as e:
            print(f"Attempt {retry_count + 1}: An error occurred - {e}")
            date -= timedelta(days=1)  # Decrement the date by one day
            retry_count += 1

    return "N/A - Maximum retries reached"

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
        #balance = get_stock_balance(api)
        accountBalance = read_balance_from_file()

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
        raw_data,date_to_use = fetch_data(url, date_to_use)

        financial_data_html = ""
        if isinstance(raw_data, list) and len(raw_data) > 0:
            formatted_df = format_dataframe(raw_data[0])
            financial_data_html = formatted_df.to_html(classes='w3-table w3-striped w3-white')
        else:
            financial_data_html = "<p>Error fetching financial data: " + str(raw_data) + "</p>"
        try:
            # Get the DataFrame from list_position
            df_positions = list_position(api,"Stock")
        except Exception as e:
            print("[EXCEPT][MAIN]The api exception happened.")
            login()
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

        #balance = get_stock_balance(api)
        accountBalance = read_balance_from_file()

        # Read the day JSON file
        df = pd.read_json('future_institutional_investors_open_interest_day.json')

        # Convert the DataFrame to HTML
        json_data_html = df.to_html(classes='w3-table w3-striped w3-white')
        
        # Read the night JSON file
        df_night = pd.read_json('future_institutional_investors_open_interest_night.json')
        
        ###### For OP################################
        # Get the current date and time
        now = datetime.now()
        # Specify the cutoff time
        cutoff = now.replace(hour=15, minute=30, second=0, microsecond=0)
        today = get_today_date()
        week_of_month = calculate_week_of_month(today)
        wednesday_of_week = calculate_wednesday_of_week(today)
        OP_WEEK = f"{today.year}{today.month:02d}W{week_of_month}"
        filename,START_WED,TODAY_DATE,OP_WEEK = get_filename(today, week_of_month, wednesday_of_week)
        df_op=load_df(filename)
        call_t_df = extract_call_oi(df_op,OP_WEEK,'買權','一般')
        put_t_df = extract_put_oi(df_op,OP_WEEK,'賣權','一般')
        print(TODAY_DATE)
        # Compare the current time with the cutoff time
        if now > cutoff:
            # If the current time is after the cutoff time, set TODAY_DATE to today
            current_date = now
        else:
            # If the current time is before the cutoff time, set TODAY_DATE to yesterday
            current_date = now - timedelta(days=1)

        # Set the time to 00:00:00
        current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        # Initialize a counter
        counter = 0

        # Check if TODAY_DATE is a weekday and exists in the DataFrame
        while True:
            TODAY_DATE = current_date.strftime('%Y/%m/%d')
            try:
                # Try to plot the figure
                fig = plot_call_put_oi(call_t_df,put_t_df,OP_WEEK,START_WED,TODAY_DATE)
                graph_html = fig.to_html(full_html=False)
                break
            except KeyError:
                # If the date does not exist in the DataFrame or is not a weekday, go to the previous day
                current_date -= timedelta(days=1)
                print(current_date)

                # Increment the counter
                counter += 1

                # If the counter reaches 14, break the loop
                if counter == 14:
                    print("No valid date found within the last 14 days.")
                    break
        try:
            graph_html = fig.to_html(full_html=False)
        except:
            graph_html = None
        ##########################################

        # Convert the DataFrame to HTML
        json_data_html_night = df_night.to_html(classes='w3-table w3-striped w3-white')
    return render_template('main.html', positions=data, total_price=total_price, total_last_price=total_last_price, total_pnl=total_pnl,accountBalance=accountBalance,financial_data_html=financial_data_html, date_to_use=date_to_use,json_data_html=json_data_html,json_data_html_night=json_data_html_night,graph_html=graph_html)

def read_counter():
    try:
        with open("counter.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        return 0

def write_counter(string):
    with open("counter.txt", "w") as file:
        file.write(str(string))

def order_cb(stat, msg):

    str_rst = read_counter()
    print(f'my_order_callback-{str_rst}')
    print(f"State:{stat}")
    print(f"msg:{msg}")
    if msg['order']['account']['account_type'] == "F":
        #The order is coming from future
        op_type = msg['operation']['op_type']
        print("Operation Type:", op_type)
        order_price = msg['order']['price']
        print(order_price)
        order_action = msg['order']['action']
        order_quantity = msg['order']['quantity']
        security_type = msg['contract']['security_type']
        data = {
        'message': f'Contract:{security_type},Type:{op_type},Direction:{order_action},價格:{order_price},數量:{order_quantity}'    # 設定要發送的訊息
        }
    elif msg['order']['account']['account_type'] == "S":
        #The order is coming from stock
        op_type = msg['operation']['op_type']
        print("Operation Type:", op_type)
        order_price = msg['order']['price']
        print(order_price)
        order_action = msg['order']['action']
        order_quantity = msg['order']['quantity']
        order_code = msg['contract']['code']
        security_type = msg['contract']['security_type']
        data = {
        'message': f'Contract:{security_type},Type:{op_type},Direction:{order_action},股票代碼:{order_code},股票名稱:{get_description_from_csv(order_code)}價格:{order_price},數量:{order_quantity}'    # 設定要發送的訊息
        }
    #LINE NOTIFIER
    data = requests.post(url, headers=headers, data=data)   # 使用 POST 方法
    '''
    line_bot_api.push_message(
    to='C4fa4a825dc69190708d673cf07f14d0a', # replace with the group ID
    messages=[TextSendMessage(text="倉別:"+f"{op_type}"+"多空:"+f"{order_action}"+f"委託價格:"+f"{order_price}")])
    '''


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print(event.message.text)
    print(event)
    data = {
    'message':'Saint Fuck University！'     # 設定要發送的訊息
    }
    '''
    #msg = "FED is a gay group"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=msg))
    '''
    '''
    if event.message.text == "Ben":
        line_bot_api.push_message(
        to='C4fa4a825dc69190708d673cf07f14d0a', # replace with the group ID
        messages=[TextSendMessage(text='Saint Fuck University')]
        )
    '''
    if event.message.text == "Ben":
        data = requests.post(url, headers=headers, data=data)   # 使用 POST 方法

def read_balance_from_file():
    # Path to the JSON file
    file_path = 'accountinfo.json'
    
    # Try to open and read the JSON file
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            accountBalance = data.get('balance', 0)  # Default to 0 if 'balance' not found
            return accountBalance
    except FileNotFoundError:
        print("accountinfo.json not found. Returning a default balance of 0.")
        return 0
    except json.JSONDecodeError:
        print("Error decoding JSON. Returning a default balance of 0.")
        return 0

def job_function():
    global api
    try:
        balance = get_stock_balance(api)
        accountBalance = balance.acc_balance
        
        # Prepare the data to write to the file
        data_to_write = {'balance': accountBalance}
        
        # Path to the JSON file
        file_path = 'accountinfo.json'
        
        # Writing the data to the JSON file
        with open(file_path, 'w') as file:
            json.dump(data_to_write, file, indent=4)
    except Exception as e:
        print(f"[get_stock_balance]The exception happened.Reason:{e}")

def login():
    global api

    try:
        # Reading the JSON file
        with open(configuration_file_path, 'r') as file:
            data = json.load(file)

        # Accessing the fields from the JSON data
        person_id_json = data['PersonID']
        password = data['Password']
        ca_path_json = data['ca_path']
        API_KEY = data['API_KEY']
        API_SECRET_KEY = data['API_SECRET_KEY']

        # First time need to add simulation=True for confirmation
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
            return jsonify({'message': f'The CA status is {result}', 'success': False})

        session['logged_in'] = True
        session['username'] = person_id_json
        return jsonify({'message': 'Reconnected successfully!', 'success': True})

    except Exception as e:
        return jsonify({'message': f'Failed to reconnect: {str(e)}', 'success': False})

# Initialize an empty dictionary to store stock data
stock_data = {}

def quote_callback(self, exchange:Exchange, tick:TickFOPv1):
    # push them to redis stream
    channel = 'Q:' + tick.code # ='Q:TXFG1' in this example 
    self.xadd(channel, {'tick':json.dumps(tick.to_dict(raw=True))})
    
filename = fr'C:\Code\MachineLearning\future_OI\stock.json'  # Update this path as needed
def read_data(filename):
    """Reads a JSON file and returns a dictionary."""
    print(filename)
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
        print(data)
        return data
    else:
        return {}

def write_data(filename, data):
    """Writes a dictionary to a JSON file."""
    print("WEIII---write_data")
    print(data)
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def add_item(data, symbol, description):
    """Adds an item to the dictionary."""
    data[symbol] = description

def delete_item(data, symbol):
    """Deletes an item from the dictionary if it exists."""
    if symbol in data:
        del data[symbol]

@app.route('/remove_stock', methods=['POST'])
def remove_stock():
    symbol = request.form['stock_symbol']
    data = read_data(filename)
    reverse_symbol = reverse_translate_string(symbol)
    delete_item(data, reverse_symbol)
    write_data(filename, data)
    return redirect(url_for('watchlist'))

# Map between numeric and alphabetic months
def numeric_to_alpha(month):
    return chr(month + 64)

def alpha_to_numeric(alphabet):
    return ord(alphabet) - 64

# Translate symbol to simplified form
def translate_string_to_simplified(input_string):
    # Extract the last two digits for the month
    month = int(input_string[-2:])
    # Convert month to the corresponding alphabet
    alphabet = numeric_to_alpha(month)

    # Return the original string with the month replaced by the alphabet and '4'
    return input_string[:3] + alphabet + "4"

# Translate simplified form back to the original symbol
def translate_string_to_original(input_string):
    # Extract the alphabet representing the month
    alphabet = input_string[3]
    # Convert the alphabet back to a numeric month
    month = str(alpha_to_numeric(alphabet)).zfill(2)

    # Extract the remaining year portion and add back the original month
    year_prefix = "2024"  # Assuming year 2024 as per example
    return input_string[:3] + year_prefix + month
    
def reverse_translate_string(input_string):
    # Extract the alphabet from the string
    alphabet = input_string[3]

    # Translate the alphabet back to its corresponding number (A=1, B=2, ..., Z=26)
    number = ord(alphabet) - 64  # ASCII value of 'A' is 65

    # Return the original string with the alphabet replaced by the number
    return input_string[:3] + "2024" + str(number).zfill(2)

@app.route('/add_stock', methods=['POST'])
def add_stock():
    symbol = request.form['stock_symbol']
    print(symbol)
    description = get_description_from_csv(symbol)  # Assuming a function that fetches this
    print(f"[add_stock]Description for", symbol, "is", description)
    data = read_data(filename)
    add_item(data, symbol, description)
    write_data(filename, data)
    if 'TXF' in symbol or 'MXF' in symbol:
        # It's a future contract
        year_month = symbol[-6:]  # Assumes the format 'TXFYYYYMM', adjust if necessary
        print(year_month)
        contract_symbol = f"{symbol[0:3]}{year_month}"
        print(f"WEI-----contract_symbol:{contract_symbol}-----")
        #mapping_symbol = translate_string(contract_symbol)
        mapping_symbol = simplify_symbol(contract_symbol)
        print(f"Will subscribe:{mapping_symbol}")
        if symbol[0:3] == "TXF":
            api.quote.subscribe(
                api.Contracts.Futures.TXF[mapping_symbol],
                quote_type=sj.constant.QuoteType.Tick, 
                version=sj.constant.QuoteVersion.v1
            )
        elif symbol[0:3] == "MXF":
            api.quote.subscribe(
                api.Contracts.Futures.MXF[mapping_symbol],
                quote_type=sj.constant.QuoteType.Tick, 
                version=sj.constant.QuoteVersion.v1
            )
    else:
        # It's a stock
        api.quote.subscribe(
            api.Contracts.Stocks[symbol],
            quote_type=sj.constant.QuoteType.Tick,
            version=sj.constant.QuoteVersion.v1
        )
    return redirect(url_for('watchlist'))
'''
@app.route('/update_watchlist_order', methods=['POST'])
def update_order():
    raw_data = request.get_json()  # Get raw JSON data
    print("Raw JSON received:", raw_data)
    new_order = raw_data.get('order')
    print("[update_order] New order received:", new_order)

    # Create a new dictionary to store the modified order
    modified_order = {}

    # Check each key-value pair in the new_order dictionary
    for key, value in new_order.items():
        # If the key matches the pattern "TXF*4"
        if re.match(r'^TXF[A-Za-z]4$', key):
            # Call reverse_translate_string function and use the result as the new key
            new_key = reverse_translate_string(key)
            modified_order[new_key] = value
        else:
            modified_order[key] = value

    # Implement logic to update the order in your database or session
    write_data(filename, modified_order)
    return jsonify({'status': 'success'})
'''
@app.route('/update_watchlist_order', methods=['POST'])
def update_order():
    raw_data = request.get_json()  # Get raw JSON data
    new_order = raw_data.get('order')

    # Read existing stock data
    stock_data = read_data(filename)

    # Create a reverse lookup for simplified symbols
    reverse_lookup = {simplify_symbol(k): k for k in stock_data.keys()}

    # Create a new ordered dictionary based on the new order
    ordered_data = OrderedDict()

    # Add symbols in the new order first
    for key in sorted(new_order, key=new_order.get):
        if key in reverse_lookup:
            original_key = reverse_lookup[key]
            ordered_data[original_key] = stock_data[original_key]

    # Add any missing keys back in their original order
    for key in stock_data:
        if key not in ordered_data:
            ordered_data[key] = stock_data[key]

    # Write the ordered data back to the file
    write_data(filename, ordered_data)
    
    return jsonify({'status': 'success'})
    
# Function to translate in either direction
def simplify_symbol(symbol):
    if symbol.startswith("TXF") or symbol.startswith("MXF"):
        if symbol[3].isdigit():  # Case: original form
            return translate_string_to_simplified(symbol)
        else:  # Case: simplified form
            return translate_string_to_original(symbol)
    return symbol

@app.route('/watchlist')
def watchlist():
    # Assuming your HTML file is named 'watchlist.html' and is stored in the 'templates' folder
    print("Wei1")
    #filename = fr'C:\Code\MachineLearning\future_OI\stock.txt'
    global stock_data  # Use the global stock_data dictionary
    if request.method == 'GET':
        # Read data from file and return it
        stock_data = read_data(filename)
        
    # Simplify symbols
    simplified_data = {simplify_symbol(k): v for k, v in stock_data.items()}
    print(simplified_data)

    return render_template('watchlist.html',symbols=simplified_data)
    
def get_description_from_csv(symbol):
    import pandas as pd
    try:
        if 'TXF' not in symbol and 'MXF' not in symbol:
            df = pd.read_csv('stock_list.csv', dtype={'code': str})  # Assuming 'code' is the column for symbols
            mapping = df.set_index('code')['name'].to_dict()

            return mapping.get(str(symbol), 'Unknown Description')  # Convert symbol to string just in case
    except Exception as e:
        print("An error occurred:", e)
        return 'Unknown Description'

def register_market_callbacks():
    # Suppose you read the symbols from a JSON file or database
    symbols = read_data(filename).keys()  # Assuming read_data returns a dictionary
    for symbol in symbols:
        if 'TXF' in symbol or 'MXF' in symbol:
            # It's a future contract
            year_month = symbol[-6:]  # Assumes the format 'TXFYYYYMM', adjust if necessary
            contract_symbol = f"{symbol[0:3]}{year_month}"
            if symbol[0:3] == "TXF":
                api.quote.subscribe(
                    api.Contracts.Futures.TXF[contract_symbol],
                    quote_type=sj.constant.QuoteType.Tick, 
                    version=sj.constant.QuoteVersion.v1
                )
            elif symbol[0:3] == "MXF":
                api.quote.subscribe(
                    api.Contracts.Futures.MXF[contract_symbol],
                    quote_type=sj.constant.QuoteType.Tick, 
                    version=sj.constant.QuoteVersion.v1
                )
        else:
            # It's a stock
            api.quote.subscribe(
                api.Contracts.Stocks[symbol],
                quote_type=sj.constant.QuoteType.Tick,
                version=sj.constant.QuoteVersion.v1
            )

@app.route('/login', methods=['GET', 'POST'])
def logi_html():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == '123' and password == '123':
            session['logged_in'] = True
            session['username'] = username  # Store username in session
            next_page = request.args.get('next') or url_for('watchlist')
            return redirect(next_page)
        else:
            flash('Invalid username or password!')
            return redirect(url_for('login', next=request.args.get('next')))
    return render_template('login.html')

@app.route('/logout')
def logout_html():
    session.pop('logged_in', None)
    session.pop('username', None)  # Clear the username from session
    return redirect(url_for('watchlist'))

def process_order(order_type, transaction_type, symbol, price,symbol_type):
    # Simulated order processing logic
    print(f"[{symbol_type}]Processing {transaction_type} order for {symbol} at {price} with {order_type} type.")
    return True

def is_all_digits(input_string):
    return input_string.isdigit()

@app.route('/order', methods=['POST'])
def order():
    global api
    order_simplified = None
    if not session.get('logged_in'):
        return jsonify({'error': 'User not logged in'}), 401

    order_type = request.form.get('order_type')  # 'market' or 'limit'
    transaction_type = request.form.get('transaction_type')  # 'buy' or 'sell'
    symbol = request.form.get('symbol')
    price = request.form.get('price')
    quantity = request.form.get('quantity')
    print("WEI------------------")

    #action (str): {Buy: 買, Sell: 賣}
    #price_type (str): {LMT: 限價, MKT: 市價, MKP: 範圍市價}
    # order_type:market,transaction_type:buy,symbol:TXFE4,price:20162
    # Call to process the order
    if order_type == "market":
        order_simplified = "MKT"
    elif order_type == "limit":
        order_simplified = "LMT"
    
    # Use getattr to dynamically get the right attribute from sj.constant.Action
    action = getattr(sj.constant.Action, transaction_type)
    price_type = getattr(sj.constant.FuturesPriceType, order_simplified)

    if 'MKT' == price_type:
        price_sent = 99
        o_type = sj.constant.OrderType.IOC
    elif "LMT" == price_type:
        price_sent = price
        o_type = sj.constant.OrderType.ROD

    if is_all_digits(symbol):
        symbol_type = "stock"
    else:
        symbol_type = "future"

    print(f"order_type:{order_type},transaction_type:{transaction_type},symbol:{symbol},symbol_type={symbol_type},price:{price},quantity:{quantity},price_type={price_type}")
    if process_order(order_type, transaction_type, symbol, price,symbol_type):
    
        '''#Stock
        contract = api.Contracts.Stocks['2890'] #取得Contract物件
        order = api.Order( #建立order內容
            price=13.8,
            quantity=1, 
            action=Action.Buy, 
            price_type=StockPriceType.LMT, 
            order_type=TFTOrderType.ROD, 
            order_lot=TFTStockOrderLot.Common, 
            account=api.stock_account
        )

        trade = api.place_order(contract, order) #執行place_order並傳入contract及order建立委託單
        print(trade) #將委託單內容輸出至console
        '''

        '''Future
        contract = api.Contracts.Futures.TXF['TXF202110'] #期貨Contract
        order = api.Order(action=Action.Buy,
            price=10200, #價格(點)
            quantity=2, #口數
            price_type=StockPriceType.LMT,
            order_type=FuturesOrderType.ROD,
            octype=FuturesOCType.Auto, #倉別，使用自動
            account=api.futopt_account #下單帳戶指定期貨帳戶
        )

        trade = api.place_order(contract, order)
        print(trade)
        '''
        #contract = api.Contracts.Futures.MXF[symbol] #取得Contract物件
        if symbol_type == "future":
            contract = getattr(api.Contracts.Futures, symbol[0:3])[symbol]
            order = api.Order(
                action=action,
                price=price,
                quantity=quantity,
                price_type=price_type,
                order_type=o_type, 
                octype=sj.constant.FuturesOCType.Auto,
                account=api.futopt_account
            )
        elif symbol_type == "stock":
            contract = api.Contracts.Stocks[symbol]
            order = api.Order(
                action=action,
                price=price,
                quantity=quantity,
                price_type=price_type,
                order_type=o_type, 
                octype=sj.constant.FuturesOCType.Auto,
                account=api.futopt_account
            )
        print(contract)
        print(getattr(api.Contracts.Futures, symbol[0:3]))
        print(simplify_symbol(symbol))
        trade = api.place_order(contract, order)

        return jsonify({'message': 'Order processed successfully'}), 200
    else:
        return jsonify({'error': 'Failed to process order'}), 500

@app.route('/show_rank/<rank_type>')
def show_rank(rank_type):
    print(f">>show_rank:{rank_type}")

    if rank_type == 'ChangePercentRank':
        scanners = api.scanners(
            scanner_type=sj.constant.ScannerType.ChangePercentRank, 
            count=5
        )
    elif rank_type == 'ChangePriceRank':
        scanners = api.scanners(
            scanner_type=sj.constant.ScannerType.ChangePriceRank, 
            count=5
        )
    elif rank_type == 'DayRangeRank':
        scanners = api.scanners(
            scanner_type=sj.constant.ScannerType.DayRangeRank, 
            count=5
        )
    elif rank_type == 'VolumeRank':
        scanners = api.scanners(
            scanner_type=sj.constant.ScannerType.VolumeRank, 
            count=5
        )
    elif rank_type == 'AmountRank':
        scanners = api.scanners(
            scanner_type=sj.constant.ScannerType.AmountRank, 
            count=5
        )
    else:
        return jsonify({'error': 'Invalid rank type'})

    df = pd.DataFrame(s.__dict__ for s in scanners)
    df.ts = pd.to_datetime(df.ts)
    df = df[['date', 'code', 'name', 'ts', 'close']]
    
    data = df.to_dict(orient='records')
    return jsonify(data)
    
@app.route('/reconnect')
def reconnect():
    global api
    api.logout()
    
    return login()

if __name__ == '__main__':

    with app.app_context():
        login()
    #api.set_context(r)
    # In order to use context, set bind=True
    #api.quote.set_on_tick_fop_v1_callback(quote_callback, bind=True)
    api.set_order_callback(order_cb)
    #api.quote.subscribe(
    #api.Contracts.Futures.TXF['TXF202403'], #期貨Contract
    #quote_type = sj.constant.QuoteType.Tick, #報價類型為Tick
    #version = sj.constant.QuoteVersion.v1, #回傳資訊版本為v1
    #)
    # Create an instance of BackgroundScheduler
    @api.on_tick_stk_v1()
    def quote_callback(exchange, tick):
        tick_data = {
            #'time': tick.datetime.strftime('%Y/%m/%d %H:%M:%S'),
            #'open': str(tick.open),
            #'high': str(tick.high),
            #'low': str(tick.low),
            'close': str(tick.close),
            #'volume': tick.volume,
            'change': str(tick.price_chg),
            'change_pct': f"{tick.pct_chg}%"
        }
        # Emit the tick data to all connected WebSocket clients
        socketio.emit('stock_data', {tick.code: tick_data})
        print(tick_data)  # Optionally, print the tick data for debugging

    # Modified quote_callback, now uses msg_queue directly instead of self
    @api.on_tick_fop_v1()
    def quote_callback(exchange, tick):
        tick_data = {
            #'time': tick.datetime.strftime('%Y/%m/%d %H:%M:%S'),
            #'open': str(tick.open),
            #'high': str(tick.high),
            #'low': str(tick.low),
            'close': str(tick.close),
            #'volume': tick.volume,
            'change': str(tick.price_chg),
            'change_pct': f"{tick.pct_chg}%"
        }
        # Emit the tick data to all connected WebSocket clients
        socketio.emit('future_data', {tick.code: tick_data})
        #print(f"Time: {tick_datetime}, Code: {tick.code}, Open: {open_price}, Close: {close_price}, High: {high_price}, Low: {low_price}, Price_chg: {price_chg}")
    scheduler = BackgroundScheduler()
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
    # Add a job to the scheduler
    scheduler.add_job(job_function, 'interval', minutes=60,misfire_grace_time=180)

    # Start the scheduler
    scheduler.start()

    # Add this call right after api.login in the main block
    register_market_callbacks()

    # Run the Flask application with SocketIO on all network interfaces
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)