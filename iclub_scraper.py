from datetime import datetime, timedelta
import logging
import re
import sys

from bs4 import BeautifulSoup
import pandas as pd
import requests


login_url = 'https://www.myiclub.com/login/index.aspx'
member_unit_ledger_url = 'https://www.myiclub.com/club/reports/member_valuation_units.aspx'

def str_to_float(float_string: str) -> float:
    """
    Remove $ sign and commas from dollar amounts and return as float
    """
    if float_string.startswith('(') and float_string.endswith(')'):
        float_string = float_string.replace('(', '-').replace(')', '')

    return float(float_string.replace('$', '').replace(',', ''))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    input_year = int(input('Ener the report year: '))
    username = input('ICLUB username: ')
    password = input('ICLUB password: ')


    with requests.Session() as s:
        login_resp = s.post(login_url, data={'user': username, 'pass': password, 'btnLogin': 'Login'})
        
        if login_resp.ok:
            logging.info(f'Login successful. Status code: {login_resp.status_code}')
        else:
            logging.error(f'Failed to login. Status code: {login_resp.status_code}')
            sys.exit(1)

        logging.info(f"Scraping myICLUB report data for year {input_year}...")
        data = []
        # Loop for 12 months plus December the previous year
        for i in range(13):
            
            if i == 0:
                month = 12
                year = input_year - 1
            else:
                month = i
                year = input_year
            
            year_month = year * 100 + month
            start_date = datetime(year, month, 1)
            next_month = start_date.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
        
            payload = {
                'club': '10175',
                'MemberID': '-1', # Current Members
                'StartDate': start_date.strftime('%m/%d/%Y'),
                'ShowLedgerEntries': 'Submit',
                'EndDate': end_date.strftime('%m/%d/%Y')
            }
            ledger_resp = s.get(member_unit_ledger_url, params=payload)
            soup = BeautifulSoup(ledger_resp.content, 'html.parser')

            for tbl in soup.find_all('table', class_='memtable'):
                
                # Get name and col headers
                thead = tbl.thead
                name = thead.tr.td.h3.string
                header_row = thead.find('tr', class_='header-row')
                header_names = {
                    i: td.get_text(' ') for i, td in enumerate(header_row.find_all('td'))
                }
            
                for tr in tbl.find_all('tr', recursive=False):
                    # Skip if empty table row
                    if tr.get_text().strip() == '':
                        continue
                    
                    row_dict = {'Name': name, 'Month': year_month}

                    # If "value as of" row, create the bootstrap row
                    if tr.has_attr('class') and tr['class'][0] == 'tab-cell':
                        for key, val in header_names.items():
                            if val == 'Date':
                                row_dict[val] = end_date
                            elif val == 'Transaction':
                                row_dict[val] = 'Ending Value'
                            else:
                                row_dict[val] = None
                        
                        # Get text after the colon and remove period at the end
                        pattern = re.compile(r'\.$')
                        acct_value_str = pattern.sub('', tr.td.get_text().split(':')[1].strip())
                        row_dict['Account Value'] = str_to_float(acct_value_str)

                    # Else loop through the td cells
                    else:
                        for j, td in enumerate(tr.find_all('td')):
                            text = td.get_text(' ').strip()
                            if text == '':
                                val = None
                            
                            elif header_names[j] == 'Date'and text is not None:
                                val = datetime.strptime(text, '%m/%d/%y')
                            elif header_names[j] in ('Unit Value', 'Paid in this date', 'Total paid in to date', 'Total paid in plus earnings to date', 'Units purchased', 'Total units'):
                                val = str_to_float(text)
                            else:
                                val = text

                            row_dict[header_names[j]] = val
                        
                        row_dict['Account Value'] = None
                    
                    data.append(row_dict)
            
    df = pd.DataFrame.from_records(data)
    df.to_csv('data_test.csv', index=False)
    logging.info('Scraping completed.')






            


