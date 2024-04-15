import shioaji as sj
import pandas as pd
import json
from shioaji import TickFOPv1, Exchange
from collections import defaultdict, deque
from decimal import Decimal
import re

import time
# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file

# Global variable for the API
api = None

def stock_test_unit(api):

    print(">>stock_test_unit")
    # 商品檔 - 請修改此處
    contract = api.Contracts.Stocks.TSE["2890"]

    # 證券委託單 - 請修改此處
    order = api.Order(
        price=18,                                       # 價格
        quantity=1,                                     # 數量
        action=sj.constant.Action.Buy,                  # 買賣別
        price_type=sj.constant.StockPriceType.MKT,      # 委託價格類別
        order_type=sj.constant.OrderType.ROD,           # 委託條件
        account=api.stock_account                       # 下單帳號
    )

    # 下單
    trade = api.place_order(contract, order)
    print(f"[stock_test_unit]Result:{trade}")
    print("<<stock_test_unit")

def futures_test_unit(api):
    
    print(">>futures_test_unit")
    # 商品檔 - 近月台指期貨, 請修改此處
    contract = min(
        [
            x for x in api.Contracts.Futures.TXF 
            if x.code[-2:] not in ["R1", "R2"]
        ],
        key=lambda x: x.delivery_date
    )

    # 期貨委託單 - 請修改此處
    order = api.Order(
        action=sj.constant.Action.Buy,                   # 買賣別
        price=17400,                                     # 價格
        quantity=1,                                      # 數量
        price_type=sj.constant.FuturesPriceType.LMT,     # 委託價格類別
        order_type=sj.constant.OrderType.ROD,            # 委託條件
        octype=sj.constant.FuturesOCType.Auto,           # 倉別
        account=api.futopt_account                       # 下單帳號
    )

    # 下單
    trade = api.place_order(contract, order)
    print(f"[futures_test_unit]Result:{trade}")
    print("<<futures_test_unit")

def get_stock_balance(api):

    balance = api.account_balance()
    print(f"The balance is {balance.acc_balance}")
    
    if balance.status:    
        return balance
    else:
        print("The query status is not working.Please check!")
        return False

def get_stock_settlements(api):

    settlements = api.settlements(api.stock_account)
    print(settlements)
    
    return settlements
def list_margin(api):

    margin = api.margin(api.futopt_account)
    print(margin.equity)
    return margin
    
#Ref link:https://sinotrade.github.io/zh_TW/tutor/accounting/margin/
def get_future_margin(api):
    
    margin = api.margin(api.futopt_account)
    print(f"The balance is {margin.available_margin}")

    if margin.status:    
        return margin
    else:
        print("The query status is not working.Please check!")
        return False

def list_accounts(api):
    
    accounts = api.list_accounts()
    print(f"The account details is {accounts}")
    
    return accounts

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
        
    accounts = api.list_accounts()
    print(f"The account details is {accounts}")

    get_stock_balance(api)
    get_future_margin(api)
    print(get_stock_settlements(api))
    
    # set context
    msg_queue = defaultdict(deque)
    api.set_context(msg_queue)
    # subscribe
    print("Dylan")
    api.quote.subscribe(
        api.Contracts.Futures.TXF['TXF202404'],
        quote_type = sj.constant.QuoteType.Tick, 
        version = sj.constant.QuoteVersion.v1
    )

    # Modified quote_callback, now uses msg_queue directly instead of self
    @api.on_tick_fop_v1()
    def quote_callback(exchange, tick):
        # Append the received tick to the deque for the corresponding contract code
        msg_queue[tick.code].append(tick)
        
        # Process the tick to extract and print OCHL values
        open_price = tick.open
        close_price = tick.close
        high_price = tick.high
        low_price = tick.low
        price_chg = tick.price_chg
        
        tick_datetime = tick.datetime.strftime('%Y/%m/%d %H:%M:%S')
        
        # Print or process the OCHL values
        print(f"Time: {tick_datetime}, Code: {tick.code}, Open: {open_price}, Close: {close_price}, High: {high_price}, Low: {low_price}, Price_chg: {price_chg}")

    api.quote.subscribe(
        api.Contracts.Stocks["2330"], 
        quote_type = sj.constant.QuoteType.Tick,
        version = sj.constant.QuoteVersion.v1
    )

    @api.on_tick_stk_v1()
    def quote_callback(exchange, tick):
        # Append the received tick to the deque for the corresponding stock code
        msg_queue[tick.code].append(tick)
        
        # Assuming TickSTKv1 includes OHLC values along with last price and volume
        open_price = tick.open
        high_price = tick.high
        low_price = tick.low
        close_price = tick.close
        volume = tick.volume
        
        tick_datetime = tick.datetime.strftime('%Y/%m/%d %H:%M:%S')
        
        # Print the stock tick information including OHLC values
        print(f"Time: {tick_datetime}, Code: {tick.code}, Open: {open_price}, High: {high_price}, Low: {low_price}, Close: {close_price}, Volume: {volume}")


    '''
    # In order to use context, set bind=True
    api.quote.set_on_tick_fop_v1_callback(quote_callback, bind=True)
    api.quote.set_on_tick_fop_v1_callback(quote_callback, bind=True) 
    '''
    # Keep the script running
    try:
        while True:
            # Keep the script alive
            time.sleep(1)  # Sleeps for 1 second before looping again
            # You can add any periodic checks or operations here
    except KeyboardInterrupt:
        print("Script terminated by user.")
