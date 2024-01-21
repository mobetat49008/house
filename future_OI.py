import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pprint import pprint
import json
from apscheduler.schedulers.blocking import BlockingScheduler

def crawl(date,market):
    print('crawling', date.strftime('%Y/%m/%d'))
    if market == "day":
        r = requests.get('https://www.taifex.com.tw/cht/3/futContractsDate?queryDate={}%2F{}%2F{}'.format(date.year, date.month,date.day))
    elif market == "night":
        r = requests.get('https://www.taifex.com.tw/cht/3/futContractsDateAh?queryDate={}%2F{}%2F{}'.format(date.year, date.month,date.day))
    if r.status_code == requests.codes.ok:
        soup = BeautifulSoup(r.text, 'html.parser')
    else:
        print('connection error')

    try:
        table = soup.find('table', class_='table_f')
        trs = table.find_all('tr')
    except AttributeError:
        print('no data for', date.strftime('%Y/%m/%d'))
        return False

    rows = trs[3:]
    data = {}
    rows_data = []
    for row in rows:
        # Extract both 'td' and 'th' elements
        cells = row.find_all(['td', 'th'])
        cells_text = [cell.get_text(strip=True) for cell in cells]
        rows_data.append(cells_text)

    current_group = None
    for row in rows_data:
        if row[0].isdigit():  # Start of a new group
            current_group = row[0] + ' ' + row[1]
            if row[1] == "英國富時100期貨":
                break
            data[current_group] = []

        if current_group:
            if row[0].isdigit():
                if market == "day":
                    selected_data = [row[2], row[7], row[13]]
                elif market == "night":
                    selected_data = [row[2], row[7]]
            else:
                if market == "day":
                    selected_data = [row[0], row[5], row[11]]
                elif market == "night":
                    selected_data = [row[0], row[5]]

            data[current_group].append(selected_data)
    return data

def main(market):
    
    date = datetime.today()
    restructured_data = {}
    print(f"Start {date} scheduleing")
    
    while True:
        data = crawl(date,market)
        if data == False:
            date = date - timedelta(days=1)
            if date < datetime.today() - timedelta(days=3):
                break
        else:
            for key, value in data.items():
                restructured_data[key] = {}
                for item in value:
                    category = item[0]  # "自營商", "投信", or "外資"
                    restructured_data[key][category] = item[1:]

            with open(f'future_institutional_investors_open_interest_{market}.json', 'w', encoding='utf-8') as f:
                print(f"Crawl finished. Ready to store daya to future_institutional_investors_open_interest_{market}.json")
                json.dump(restructured_data, f, ensure_ascii=False, indent=4)
            break


if __name__ == '__main__':


    # Create a scheduler instance
    scheduler = BlockingScheduler()

    # Schedule the function to be called every day at 3:00 PM
    scheduler.add_job(main, 'cron', hour=15, minute=0,args=['day'])

    # Schedule the same function to be called every day at 6:00 AM
    scheduler.add_job(main, 'cron', hour=6, minute=0,args=['night'])

    # Start the scheduler
    scheduler.start()
