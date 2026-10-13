"""
tools.py  —  CONCEPT 3: Tools
=============================

🧠 What is a Tool?
------------------
An LLM can only produce text. It cannot browse the internet or look up
today's stock price. A TOOL is a normal Python function that we allow the
LLM to "call" when it needs real data.

How it works:
  1. We decorate a function with `@tool`.
  2. LangChain reads the function NAME, ARGUMENTS and DOCSTRING and
     describes the tool to the LLM.  -> The docstring is VERY important:
     it's how the LLM decides WHEN to use the tool.
  3. When the LLM wants data, it replies with a "tool call" like
         {"name": "get_stock_news", "args": {"ticker": "AAPL"}}
     instead of a normal answer.
  4. LangGraph's `ToolNode` runs the function and gives the result back to
     the LLM (see news_subgraph.py for this loop in action).

Two ways we use tools in this project:
  • Called BY THE LLM (agent style)    -> news_subgraph.py
  • Called DIRECTLY by our own code     -> nodes.py (fundamental & technical)
    using  `get_fundamentals.invoke({"ticker": "AAPL"})`

All data comes from Yahoo Finance via the free `yfinance` library.
  US stocks:    AAPL, MSFT, NVDA ...
  Indian NSE:   RELIANCE.NS, TCS.NS, INFY.NS ...
  Indian BSE:   RELIANCE.BO, 500325.BO ...
"""

from datetime import datetime

import yfinance as yf
from langchain_core.tools import tool


def _fmt(value, kind: str = "num") -> str:
    """Small helper to print numbers nicely. Returns 'N/A' if data is missing."""
    if value is None:
        return "N/A"
    if kind == "pct":
        return f"{value * 100:.2f}%"
    if kind == "big":  # e.g. market cap: 2.5T, 340.2B, 12.1M
        for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
            if abs(value) >= size:
                return f"{value / size:.2f}{unit}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


@tool
def get_stock_price(ticker: str) -> str:
    """Get the latest stock price and today's change for a ticker symbol (e.g. AAPL, TCS.NS)."""
    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        return f"No price data found for '{ticker}'. The ticker may be wrong."

    return (
        f"{info.get('longName', ticker)} ({ticker})\n"
        f"Price: {_fmt(price)} {info.get('currency', '')}\n"
        f"Previous close: {_fmt(info.get('previousClose'))}\n"
        f"Day range: {_fmt(info.get('dayLow'))} - {_fmt(info.get('dayHigh'))}"
    )


@tool
def get_fundamentals(ticker: str) -> str:
    """Get key fundamental data (valuation, profitability, growth, debt) for a ticker symbol."""
    info = yf.Ticker(ticker).info
    if not info or info.get("longName") is None:
        return f"No fundamental data found for '{ticker}'."

    return "\n".join(
        [
            f"Company: {info.get('longName')}  |  Sector: {info.get('sector', 'N/A')}  |  Industry: {info.get('industry', 'N/A')}",
            f"Currency: {info.get('currency', 'N/A')}",
            f"Market Cap: {_fmt(info.get('marketCap'), 'big')}",
            f"P/E (trailing): {_fmt(info.get('trailingPE'))}   P/E (forward): {_fmt(info.get('forwardPE'))}",
            f"Price/Book: {_fmt(info.get('priceToBook'))}",
            f"Profit Margin: {_fmt(info.get('profitMargins'), 'pct')}",
            f"Return on Equity: {_fmt(info.get('returnOnEquity'), 'pct')}",
            f"Revenue Growth (YoY): {_fmt(info.get('revenueGrowth'), 'pct')}",
            f"Earnings Growth (YoY): {_fmt(info.get('earningsGrowth'), 'pct')}",
            f"Debt/Equity: {_fmt(info.get('debtToEquity'))}",
            f"Dividend Yield: {_fmt(info.get('dividendYield'))}%",
            f"Analyst target price (mean): {_fmt(info.get('targetMeanPrice'))}",
            f"Business summary: {(info.get('longBusinessSummary') or 'N/A')[:500]}",
        ]
    )


@tool
def get_price_history(ticker: str) -> str:
    """Get 1 year of price history summarised as technical indicators (moving averages, returns, volatility)."""
    history = yf.Ticker(ticker).history(period="1y")
    # BSE (.BO) tickers sometimes have very little history on Yahoo Finance.
    if len(history) < 30:
        return f"Not enough price history for '{ticker}'. If this is a BSE (.BO) ticker, try the NSE (.NS) one."

    close = history["Close"]  # a pandas Series of daily closing prices
    latest = close.iloc[-1]

    # Simple Moving Averages: the average closing price of the last N days.
    sma_50 = close.tail(50).mean()
    sma_200 = close.tail(200).mean()

    # Returns: % change from N trading days ago until today.
    def pct_change(days: int) -> str:
        if len(close) <= days:
            return "N/A"
        return f"{(latest / close.iloc[-days - 1] - 1) * 100:.2f}%"

    # Volatility: how much the daily price jumps around (annualised).
    volatility = close.pct_change().std() * (252**0.5) * 100

    return "\n".join(
        [
            f"Latest close: {latest:.2f}",
            f"50-day moving average: {sma_50:.2f}",
            f"200-day moving average: {sma_200:.2f}",
            f"Price vs 50-day MA: {'ABOVE' if latest > sma_50 else 'BELOW'}",
            f"Price vs 200-day MA: {'ABOVE' if latest > sma_200 else 'BELOW'}",
            f"52-week high: {close.max():.2f}   52-week low: {close.min():.2f}",
            f"Return 1 month: {pct_change(21)}   3 months: {pct_change(63)}   1 year: {pct_change(len(close) - 1)}",
            f"Annualised volatility: {volatility:.1f}%",
        ]
    )


@tool
def get_stock_news(query: str) -> str:
    """Search the latest news headlines about a company.

    `query` can be a US ticker (e.g. 'AAPL') or a company name.
    For Indian stocks, search by COMPANY NAME (e.g. 'Tata Consultancy Services'),
    because searching '.NS' tickers usually finds nothing.
    If no news is found, try again with a different query (short name, full name or ticker).
    """
    news_items = yf.Search(query, news_count=8).news
    if not news_items:
        return f"No recent news found for '{query}'. Try a different query."

    lines = []
    for item in news_items:
        published = datetime.fromtimestamp(item.get("providerPublishTime", 0)).date()
        lines.append(f"- [{published}] {item.get('title', 'No title')}  ({item.get('publisher', '')})")
    return "\n".join(lines)


# The list of tools the NEWS AGENT (LLM) is allowed to call.
NEWS_AGENT_TOOLS = [get_stock_news, get_stock_price]
