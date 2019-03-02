import gspread
import sqlite3
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from dateutil.relativedelta import relativedelta

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope))


def test(sheetid):
    sh = gc.open_by_key(sheetid).sheet1
    values = sh.get_all_values()
    for row in values:
        print(row)


def read_sheet(sheet_id):
    sh = gc.open_by_key(sheet_id).sheet1
    values = sh.get_all_values()[1:]

    connection = sqlite3.connect("database.db")
    cursor = connection.cursor()
    cursor.execute("""DROP TABLE IF EXISTS subscriptions""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS subscriptions(
                      transaction_id TEXT UNIQUE,
                      discord_id INTEGER,
                      purchase_date FLOAT,
                      duration INTEGER,
                      end_date FLOAT
                      );""")

    for row in values:
        duration = getduration(row[4])
        date, end_date = get_dates(row[0], duration)
        cursor.execute("""REPLACE INTO subscriptions VALUES (?, ?, ?, ?, ?)""",
                       (row[6], int(row[2]), date, duration, end_date))

    connection.commit()
    connection.close()


def getduration(text):
    text = text.lower()
    if text in ["1month", "1 month", "30 days", "1 month (30 days)"]:
        return 30
    elif text in ["3months", "3 months", "90 days", "3 months (90 days)"]:
        return 90
    elif text in ["6months", "6 months", "180 days", "6 months (180 days)"]:
        return 180
    elif text in ["12months", "12 months", "90 days", "12 months (360 days)", "year", "1 year"]:
        return 360
    elif text in ["lifetime", "lifetime access", "life time (until death)", "life time"]:
        return None
    else:
        print(f"Invalid time format found [{text}]")
        return None


def get_dates(date, duration):
    date = datetime.strptime(date, "%d/%m/%Y %H:%M:%S")
    if duration is None:
        end = None
    else:
        end = (date + relativedelta(days=+duration)).timestamp()
    return date.timestamp(), end


def get_all_users():
    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("""SELECT DISTINCT discord_id FROM subscriptions""")
    data = cursor.fetchall()
    connection.commit()
    connection.close()
    return data


def get_user_purchases(userid):
    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("""SELECT * FROM subscriptions WHERE discord_id = ? ORDER BY purchase_date ASC""", userid)
    data = cursor.fetchall()
    connection.commit()
    connection.close()
    return data


def get_all_rows():
    connection = sqlite3.connect("database.db")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("""SELECT * FROM subscriptions ORDER BY purchase_date ASC""")
    data = cursor.fetchall()
    connection.commit()
    connection.close()
    return data
