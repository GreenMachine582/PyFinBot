import yfinance as yf

ticker = yf.Ticker("TNE.AX")
dividends = ticker.dividends
# Filter by date
dividends = dividends[dividends.Date >= "2020-01-01"]
print(dividends)
