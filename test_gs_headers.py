from shared.google_client import GoogleSheetClient
import sys

client = GoogleSheetClient()
sheet = client._get_sheet("cms")
if sheet:
    print("HEADERS:", sheet.row_values(1))
else:
    print("SHEET NOT FOUND")
