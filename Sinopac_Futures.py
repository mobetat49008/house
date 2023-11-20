import shioaji as sj
import json

# Path to the JSON file
configuration_file_path = r'C:\Code\Configuration\Sinopac_future.json'  # Replace with the actual path of your JSON file

def stock_test_unit(api):

    print(">>stock_test_unit")
    # 商品檔 - 請修改此處
    contract = api.Contracts.Stocks.TSE["2890"]

    # 證券委託單 - 請修改此處
    order = api.Order(
        price=18,                                       # 價格
        quantity=1,                                     # 數量
        action=sj.constant.Action.Buy,                  # 買賣別
        price_type=sj.constant.StockPriceType.LMT,      # 委託價格類別
        order_type=sj.constant.OrderType.ROD,           # 委託條件
        account=api.stock_account                       # 下單帳號
    )

    # 下單
    trade = api.place_order(contract, order)
    stock_test_unit
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
        price=15000,                                     # 價格
        quantity=1,                                      # 數量
        price_type=sj.constant.FuturesPriceType.LMT,     # 委託價格類別
        order_type=sj.constant.OrderType.ROD,            # 委託條件
        octype=sj.constant.FuturesOCType.Auto,           # 倉別
        account=api.futopt_account                       # 下單帳號
    )

    # 下單
    trade = api.place_order(contract, order)
    print("<<futures_test_unit")


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
    
    stock_test_unit(api)
    futures_test_unit(api)
    
    '''
    #Set default feature account
    api.set_default_account(accounts[0])
    print(api.futopt_account)
    
    #Set default stock account
    api.set_default_account(accounts[1])
    print(api.stock_account)

    api.list_positions(api.stock_account)
    '''
    
    