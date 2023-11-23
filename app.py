from flask import Flask
from flask import render_template
from Sinopac_Futures import list_accounts,list_position,get_stock_balance

import shioaji as sj
import pandas as pd
import json
import pandas as pd
import requests

# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file
app = Flask(__name__)

# Global variable for the API
api = None

@app.route('/')
def main():
    global api
    data = []

    if api:
        # Get the DataFrame from list_position
        df_positions = list_position(api)

        # Read the JSON file into a DataFrame
        df_json = pd.read_json('stock_number.json', orient='records', lines=True)

        # Convert keys in the dictionary to strings
        code_to_name = {str(key): value for key, value in zip(df_json[2], df_json[3])}
        print(df_positions)
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