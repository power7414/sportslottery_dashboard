import pandas as pd

s = pd.Series(['2025/5/31', '2025-03-09'])
print("Without replace:")
print(pd.to_datetime(s, errors='coerce'))

print("\nWith replace:")
print(pd.to_datetime(s.str.replace('/', '-'), errors='coerce'))
