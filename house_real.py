import requests
import os
import sys
import zipfile
import time
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import RadioButtons
import tkinter as tk
from tkinter import ttk

# Global configurations
plt.rcParams['font.size'] = 20
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# Dictionary mapping city names to codes
city_codes = {
    "臺北市": "A",
    "臺中市": "B",
    "基隆市": "C",
    "臺南市": "D",
    "高雄市": "E",
    "新北市": "F",
    "宜蘭縣": "G",
    "桃園縣市": "H",
    "新竹縣": "J",
    "苗栗縣": "K",
    "臺中縣": "L",
    "南投縣": "M",
    "彰化縣": "N",
    "雲林縣": "P",
    "嘉義縣": "Q",
    "臺南縣": "R",
    "高雄縣": "S",
    "屏東縣": "T",
    "花蓮縣": "U",
    "臺東縣": "V",
    "澎湖縣": "X",
    "陽明山": "Y",
    "金門縣": "W",
    "連江縣": "Z",
    "嘉義市": "I",
    "新竹市": "O",
}

def select_city():
    """
    Opens a Tkinter dialog to select a city and returns the corresponding code.
    """
    result = {'city_code': None}

    def on_city_selected():
        result['city_code'] = city_codes[city_selector.get()]
        root.destroy()  # Close the Tkinter window after selection

    root = tk.Tk()
    root.title("Select City")

    city_selector = ttk.Combobox(root, values=list(city_codes.keys()), state="readonly")
    city_selector.grid(column=0, row=0)
    city_selector.current(0)  # Optional: set the default selection

    select_button = tk.Button(root, text="Select", command=on_city_selected)
    select_button.grid(column=0, row=1)

    root.mainloop()
    return result['city_code']  # Return the selected city code after the Tkinter window is closed

# Function to plot data based on the selected year
def plot_year_histogram(year, df, fig, ax):
    plt.figure(fig.number)  # Ensure this is the current figure
    ax.clear()  # Clear the existing plot on the axis
    df_selected_year = df[df['year'] == year]
    
    for district in set(df_selected_year['鄉鎮市區']):
        df_district = df_selected_year[df_selected_year['鄉鎮市區'] == district]
        # Divide the values by 1000 to convert to 千元
        (df_district['單價元坪'][df_district['單價元坪'] < 2000000] / 1000).hist(bins=120, alpha=0.7, ax=ax)

    ax.set_xlim(0, 2000)  # Update the x-axis limit to 2000 (千元)
    ax.legend(set(df_selected_year['鄉鎮市區']))
    ax.set_title(f'Histogram for {year} (單價元坪)')  # Update the title
    ax.set_xlabel('Price (千元)')  # Update the x-axis label to indicate 千元
    ax.set_ylabel('Frequency (次數)')
    ax.grid(True)  # Add grid
    fig_hist.canvas.draw_idle()  # Ensure the figure updates

def plot_price_history(ax, prices):
    ax.clear()  # Clear the existing plot on the axis
    price_history = pd.DataFrame(prices)
    for district in price_history.columns:
        price_history[district].plot(ax=ax, label=district, marker='o')  # Add dots
    price_history.mean(axis=1).plot(ax=ax, label='Mean', linestyle='--', color='black', marker='o')  # Add dots
    ax.legend(fontsize="small", loc="upper left", bbox_to_anchor=(1.0, 1.0))  # Adjusting font size and position
    format_plot(ax, title="Price History by District")
    ax.grid(True)  # Add grid
    ax.figure.subplots_adjust(right=0.75)  # Adjust the right boundary of the subplot to make space for the legend

def plot_price_building_type(ax, df):
    building_type_prices = {}
    for building_type in set(df['建物型態2']):
        cond = (
            (df['主要用途'] == '住家用')
            & (df['單價元坪'] < df["單價元坪"].quantile(0.8))
            & (df['單價元坪'] > df["單價元坪"].quantile(0.2))
            & (df['建物型態2'] == building_type)
        )
        building_type_prices[building_type] = df[cond]['單價元坪'].groupby(df[cond]['year']).mean().loc[107+1911:112+1911]

    ax.clear()  # Clear the existing plot on the axis
    pd.DataFrame(building_type_prices)[['公寓', '住宅大樓', '套房', '華廈']].plot(ax=ax, marker='o')
    ax.legend(fontsize="small", loc="upper left", bbox_to_anchor=(1.0, 1.0))  # Adjusting font size and position
    ax.set_title("Price by Building Type")
    ax.grid(True)  # Add grid
    ax.figure.subplots_adjust(right=0.75)  # Adjust the right boundary of the subplot to make space for the legend

# Function to handle RadioButtons value change
def update(label):
    year = int(label)  # Get the selected year from the label
    with plt.rc_context({'axes.titlepad': 20}):  # Adjust title padding
        plot_year_histogram(year, df, ax_hist)
        plot_price_history(ax_line_district, prices)
        plot_price_building_type(ax_line_building_type, building_type_prices)
    plt.draw()

# Function to format plots
def format_plot(ax, title=None):
    ax.grid(True)
    ax.legend(title='District', bbox_to_anchor=(1.05, 1), loc='upper left')
    if title:
        ax.set_title(title)

# Function to download and extract real estate data
def real_estate_crawler(year, season):
    if year > 1000:
        year -= 1911

    res = requests.get(f"https://plvr.land.moi.gov.tw//DownloadSeason?season={year}S{season}&type=zip&fileName=lvr_landcsv.zip")
    print(res)

    fname = f"{year}{season}.zip"
    with open(fname, 'wb') as f:
        f.write(res.content)

    folder = f'real_estate{year}{season}'
    if not os.path.exists(folder):
        os.mkdir(folder)

    with zipfile.ZipFile(fname, 'r') as zip_ref:
        zip_ref.extractall(folder)
    
    time.sleep(10)

def gather_building_type_prices(df):
    building_type_prices = {}
    for building_type in set(df['建物型態2']):
        cond = (
            (df['主要用途'] == '住家用')
            & (df['建物型態2'] == building_type)
            & (df['單價元坪'] < df["單價元坪"].quantile(0.95))
            & (df['單價元坪'] > df["單價元坪"].quantile(0.05))
        )
        groups = df[cond]['year']
        building_type_prices[building_type] = df[cond]['單價元坪'].astype(float).groupby(groups).mean().loc[107+1911:112+1911]
    return building_type_prices

# Main function
def main():
    global fig_hist  # Declare fig_hist as global so it can be accessed within plot_year_histogram
    plt.ion()  # Turn on interactive mode
    
    # GUI for city selection
    selected_code = select_city()
    if selected_code is not None:
        selected_code = selected_code.lower()  # Lowercase the selected city code
    else:
        print("No city was selected. Exiting.")
        return  # Exit the function if no city was selected

    # Uncomment below lines if you wish to fetch data again
    # for year in range(107, 113):
    #     for season in range(1, 5):
    #         print(year, season)
    #         real_estate_crawler(year, season)
    dirs = [d for d in os.listdir() if d.startswith('real')]
    dfs = []

    for d in dirs:
        # Use the selected city code to construct the file name
        file_name = f"{selected_code}_lvr_land_a.csv"
        full_path = os.path.join(d, file_name)
        if os.path.exists(full_path):  # Check if the file exists before reading
            df_temp = pd.read_csv(full_path, index_col=False)
            df_temp['Q'] = d[-1]
            dfs.append(df_temp.iloc[1:])
        else:
            print(f"File not found: {full_path}")

    df = pd.concat(dfs, sort=True)
    df['year'] = df['交易年月日'].str[:-4].astype(int) + 1911
    df['單價元平方公尺'] = df['單價元平方公尺'].astype(float)
    df['單價元坪'] = df['單價元平方公尺'] * 3.30579
    df['建物型態2'] = df['建物型態'].str.split('(').str[0]
    df = df[df['備註'].isnull()]
    df.index = pd.to_datetime((df['交易年月日'].str[:-4].astype(int) + 1911).astype(str) + df['交易年月日'].str[-4:], errors='coerce')

    # Line graph for Price History by District
    prices = {}
    for district in set(df['鄉鎮市區']):
        cond = (
            (df['主要用途'] == '住家用')
            & (df['鄉鎮市區'] == district)
            & (df['單價元坪'] < df["單價元坪"].quantile(0.95))
            & (df['單價元坪'] > df["單價元坪"].quantile(0.05))
        )
        groups = df[cond]['year']
        prices[district] = df[cond]['單價元坪'].astype(float).groupby(groups).mean().loc[107+1911:112+1911]

    building_type_prices = gather_building_type_prices(df)  # Gather building type prices
   # Create separate figures for each plot
    fig_hist, ax_hist = plt.subplots(figsize=(15, 10))
    fig_line_district, ax_line_district = plt.subplots(figsize=(15, 10))
    fig_line_building_type, ax_line_building_type = plt.subplots(figsize=(15, 10))

    # Initial plots
    with plt.rc_context({'axes.titlepad': 20}):  # Adjust title padding
        plot_year_histogram(2018, df, fig_hist, ax_hist)  # Initial plot for 2018
        plot_price_history(ax_line_district, prices)
        plot_price_building_type(ax_line_building_type, df)  # Pass df, not building_type_prices

    year_names = [str(year) for year in range(2018, 2024)]
    rax = plt.axes([0.05, 0.7, 0.15, 0.15], frameon=False)  # Adjust the position and size of the RadioButtons widget
    # You might need to reduce the font size for the radio buttons to prevent overlapping.
    with plt.rc_context({'font.size': 12}):
        radio = RadioButtons(rax, year_names)
        
    #radio = RadioButtons(rax, year_names, orientation="vertical")

    def update(label):
        year = int(label)  # Get the selected year from the label
        with plt.rc_context({'axes.titlepad': 20}):  # Adjust title padding
            plot_year_histogram(year, df, fig_hist, ax_hist)  # Pass fig_hist as well
            plot_price_history(ax_line_district, prices)
        plt.draw()

    radio.on_clicked(update)  # Set up the RadioButtons to call update whenever the selected item changes

    plt.ioff()  # Turn off interactive mode
    plt.show()  # Keep the plots open

if __name__ == '__main__':
    main()

