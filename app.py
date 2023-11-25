from flask import Flask,render_template, jsonify
from Sinopac_Futures import list_accounts,list_position,get_stock_balance,list_margin

import shioaji as sj
import pandas as pd
import json
import pandas as pd
import requests
import math

# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file
app = Flask(__name__)

# Global variable for the API
api = None

# Example function to replace NaN values
def replace_nan(val):
    if isinstance(val, float) and math.isnan(val):
        return None  # or return "" if you prefer an empty string
    return val

@app.route('/stock_data')
def stock_data():
    global api
    data = []

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
        top_profit = df_positions.nlargest(10, 'Profit Percentage')[['Chinese Name', 'Profit Percentage']]
        top_stock = df_positions.nlargest(10, 'Stock Percentage')[['Chinese Name', 'Stock Percentage']]

        # Convert back to string format with '%' for display
        top_profit['Profit Percentage'] = top_profit['Profit Percentage'].apply(lambda x: f'{x:.2f}%')
        top_stock['Stock Percentage'] = top_stock['Stock Percentage'].apply(lambda x: f'{x:.2f}%')

        data = df_positions.to_dict(orient='records')
        balance = get_stock_balance(api)
        accountBalance = balance.acc_balance

        for position in data:
            for key, value in position.items():
                position[key] = replace_nan(value)

        # Package everything into a dictionary to be returned as JSON
        response_data = {
            "positions": data,
            "total_price": total_price,
            "total_last_price": total_last_price,
            "total_pnl": total_pnl,
            "accountBalance": accountBalance,
            "top_profit_data": top_profit.to_dict(orient='records'),
            "top_stock_data": top_stock.to_dict(orient='records')
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

    if api:
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
    return render_template('main.html', positions=data, total_price=total_price, total_last_price=total_last_price, total_pnl=total_pnl,accountBalance=accountBalance)

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