import urllib3
from bs4 import BeautifulSoup
import os

#資料處理套件
import pandas as pd
from datetime import datetime, date, timedelta
import numpy as np

#畫圖套件
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def get_option(commodity_id, queryStartDate, queryEndDate):

    # 用urllib3下載選擇權每日交易行情資料
    http = urllib3.PoolManager()
    url = "https://www.taifex.com.tw/cht/3/dlOptDataDown"
    res = http.request(
         'POST',
          url,
          fields={
             'down_type': 1,
             'commodity_id': commodity_id,
             'queryStartDate': queryStartDate,
             'queryEndDate': queryEndDate
          }
     )
    html_doc = res.data
    
    # 用BeautifulSoup解析資料
    soup = BeautifulSoup(html_doc, 'html.parser')
    soup_str = str(soup)
    lines = soup_str.split('\r\n')

    # 新增空的dataframe,定義欄位名稱
    df = pd.DataFrame(columns = lines[0].split(','))

    # 把選擇權資料一行一行寫入dataframe內
    for i in range(1, len(lines) - 1):
        list_ = lines[i].split(',')[:-1]
        df_length = len(df)
        df.loc[df_length] = list_
        
    # 資料轉型
    for col in [0, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]:
        for row in range(df.shape[0]):
            # 把"日期"從字串(string)換成時間(datetime)
            if col == 0:
                day = df.iloc[row,0].split('/')
                df.iloc[row, 0] = datetime(int(day[0]), int(day[1]), int(day[2]))  
            # 把"履約價"改成沒有小數點的字串
            elif col == 3:
                price = df.iloc[row,3].split('.')
                df.iloc[row,3] = str(price[0])
            # 把字串(string)換成浮點數(float): "履約價", "開盤價", "最高價", "最低價", "收盤價", "成交量", "結算價", "未沖銷契約數", "最後最佳買價", "最後最佳賣價", "歷史最高價", "歷史最低價" 
            elif col != 0 and df.iloc[row, col] != '-':
                df.iloc[row, col] = float(df.iloc[row,col])

    return df

def extract_call_oi(df,week,option,time):
    call_df = df.loc[(df['到期月份(週別)'] == week) & \
                (df['買賣權'] == option) & \
                (df['交易時段'] == time)]
    
    # 取得 dataframe index
    index = call_df['履約價'].unique()
    idx = np.sort(index)
    
    # 取得 dataframe 欄位名稱
    dates = call_df['交易日期'].unique()

    # 建立 dataframe 包含 index 與欄位名稱
    call_t_df = pd.DataFrame(index = idx, columns = list(dates))

    # 取出各日期的未沖銷契約數 依序放入 dataframe 中
    for col in call_t_df.columns:
        call_t_df[col] = call_df.loc[call_df['交易日期'] == col].set_index('履約價')['未沖銷契約數']
        
    #空值填入 0
    call_t_df = call_t_df.fillna(0)
    #print(call_t_df)
    print(call_t_df.columns)
    # Convert all columns in call_t_df to numeric, if they are not already
    for col in call_t_df.columns:
        call_t_df[col] = pd.to_numeric(call_t_df[col], errors='coerce')
    
    return call_t_df
    
def extract_put_oi(df,week,option,time):

    put_df = df.loc[(df['到期月份(週別)'] == week) & \
                (df['買賣權'] == '賣權') & \
                (df['交易時段'] == '一般')]
    index = put_df['履約價'].unique()
    idx = np.sort(index)
    # 取得 dataframe 欄位名稱
    dates = put_df['交易日期'].unique()
    # 建立 dataframe 包含 index 與欄位名稱
    put_t_df = pd.DataFrame(index = idx, columns = list(dates))
    # 取出各日期的未沖銷契約數 依序放入 dataframe 中
    for col in put_t_df.columns:
        put_t_df[col] = put_df.loc[put_df['交易日期'] == col].set_index('履約價')['未沖銷契約數']

    # Convert to float first (this also handles NaN values)
    put_t_df = put_t_df.astype('float')
    #空值填入 0
    put_t_df = put_t_df.fillna(0)
    print(put_t_df.columns)
    return put_t_df

def plot_call_put_oi(call_t_df,put_t_df,week,START_WED,today):
    
    START_WED = datetime.strptime(START_WED, '%Y/%m/%d')
    today = datetime.strptime(today, '%Y/%m/%d')
    
    # 設定左右子圖
    fig = make_subplots(
        rows=1, 
        cols=2, 
        horizontal_spacing = 0.05, 
        subplot_titles = ("買權", "賣權")
    )

    # 畫買權長條圖
    fig.add_trace(go.Bar(y = call_t_df.index,
                         x = -call_t_df[f'{START_WED}'],
                         orientation = 'h',
                         name = 'Call',
                         text = ("(" + (call_t_df[f'{START_WED}'] - call_t_df[f'{today}']).astype('int').astype('str') + ") " + call_t_df[f'{START_WED}'].astype('int').astype('str')),
                         marker = dict(color = 'red')), 
                  row = 1, 
                  col = 1)

    # 畫賣權長條圖
    fig.add_trace(go.Bar(y = put_t_df.index,
                         x = put_t_df[f'{START_WED}'],
                         orientation = 'h',
                         name = 'Put',
                        text = (put_t_df[f'{START_WED}'].astype('int').astype('str') + " (" + 
                                (put_t_df[f'{START_WED}'] - put_t_df[f'{today}']).astype('int').astype('str') + ")"),
                         marker = dict(color = 'green')), 
                  row = 1, 
                  col = 2)


    # 設定圖的x跟y軸標題
    fig.update_xaxes(tickvals = [-15000, -12500, -10000, -7500, -5000, -2500, 0],
                     ticktext = ['15k', '12.5k', '10k', '7.5k', '5k', '2.5k', '0'], 
                     title_text = "未沖銷契約數",
                     row = 1, 
                     col = 1)

    fig.update_xaxes(tickvals = [0, 2500, 5000, 7500, 10000, 12500, 15000],
                     ticktext = ['0', '2.5k', '5k', '7.5k', '10k', '12.5k', '15k'], 
                     title_text = "未沖銷契約數",
                     row = 1, 
                     col = 2)

    fig.update_yaxes(autorange = "reversed", 
                     showticklabels = False, 
                     title_text = "履約價",
                     row = 1, 
                     col = 1)

    fig.update_yaxes(autorange = "reversed", 
                     row = 1, 
                     col = 2)



    # 設定圖的標題跟長寬
    fig.update_layout(title_text = f"臺指選擇權[{week}] - {today} 未沖銷契約數 支撐壓力圖", 
                      width = 1000, 
                      height = 1300)
                      
    return fig

def get_today_date():
    # 獲取今天的日期
    today = datetime.today()
    return today

def calculate_week_of_month(today):
    # 計算今天是這個月的第幾個星期三
    if today.weekday() == 2:
        week_of_month = (today.day - 1) // 7 + 2
    else:
        week_of_month = (today.day - 1) // 7 + 1
    return week_of_month

def calculate_wednesday_of_week(today):
    # 計算這個禮拜起始的禮拜三日期
    start_of_week = today - timedelta(days=today.weekday())
    wednesday_of_week = start_of_week + timedelta(days=2)
    return wednesday_of_week

def get_filename(today, week_of_month, wednesday_of_week):
    OP_WEEK = f"{today.year}{today.month:02d}W{week_of_month}"
    START_WED = f"{wednesday_of_week.year}/{wednesday_of_week.month:02d}/{wednesday_of_week.day:02d}"
    TODAY_DATE = f"{today.year}/{today.month:02d}/{today.day:02d}"

    START_WED_FORMATED = f"{wednesday_of_week.year}-{wednesday_of_week.month:02d}-{wednesday_of_week.day:02d}"
    TODAY_DATE_FORMATED = f"{today.year}-{today.month:02d}-{today.day:02d}"

    filename = fr'C:\Code\MachineLearning\future_OI\option_data_{OP_WEEK}_{START_WED_FORMATED}_{TODAY_DATE_FORMATED}.csv'

    return filename,START_WED,TODAY_DATE,OP_WEEK

def load_or_create_df(filename, START_WED, TODAY_DATE):

    # Get the DataFrame by calling the function
    df = get_option(commodity_id='TXO', 
                    queryStartDate=START_WED, 
                    queryEndDate=TODAY_DATE)
    # Save the DataFrame to a CSV file for future use
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"The {filename} is generated")
    return df
    
def load_df(filename):

    # Save the DataFrame to a CSV file for future use
    df=pd.read_csv(filename)

    return df

def export_main():
    today = get_today_date()
    week_of_month = calculate_week_of_month(today)
    wednesday_of_week = calculate_wednesday_of_week(today)
    filename,START_WED,TODAY_DATE,OP_WEEK = get_filename(today, week_of_month, wednesday_of_week)
    df = load_or_create_df(filename, START_WED, TODAY_DATE)

if __name__ == "__main__":
    today = get_today_date()
    week_of_month = calculate_week_of_month(today)
    wednesday_of_week = calculate_wednesday_of_week(today)
    filename,START_WED,TODAY_DATE,OP_WEEK = get_filename(today, week_of_month, wednesday_of_week)
    df = load_or_create_df(filename, START_WED, TODAY_DATE)

    ##########################Call part##########################
    call_t_df = extract_call_oi(df,OP_WEEK,'買權','一般')
    #################################################################
    ##########################Put part##########################
    put_t_df = extract_put_oi(df,OP_WEEK,'賣權','一般')
    #################################################################

    fig = plot_call_put_oi(call_t_df,put_t_df,OP_WEEK,START_WED,TODAY_DATE)
    fig.show()
