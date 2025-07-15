# To get net units held by a user for a stock as of a particular date:
"""
SELECT
    s.symbol,
    SUM(CASE t.type WHEN 'Buy' THEN t.units ELSE -t.units END) AS total_units
FROM transaction t
JOIN stock s ON t.stock_id = s.id
WHERE t.user_id = :user_id
  AND t.date <= :target_date
GROUP BY s.symbol;
"""

# To determine the capital gain or loss for a given financial year (FY), you'll want to:
# 1. Filter all Sell transactions within the desired FY.
# 2. For each sell, determine the cost basis of the units sold — commonly using FIFO (First-In-First-Out) unless another method is preferred.
# 3. Subtract the cost basis from the proceeds (value - fee) to get capital gain or loss.
"""
SELECT
    t.id,
    t.stock_id,
    s.symbol,
    t.type,
    t.date,
    t.units,
    t.price,
    t.fee,
    t.value,
    t.cost,
    t.fy
FROM transaction t
JOIN stock s ON t.stock_id = s.id
WHERE t.user_id = :user_id
  AND t.fy = :fy
ORDER BY t.date ASC, t.id ASC;
"""

from collections import deque
from decimal import Decimal
from typing import List, Dict

def calculate_capital_gain_loss(transactions: List[Dict]) -> List[Dict]:
    """Apply FIFO matching to calculate gain/loss for each sell transaction."""
    results = []
    buys = deque()

    for txn in transactions:
        txn_type = txn["type"]
        units = Decimal(str(txn["units"]))  # Safer with Decimal
        value = Decimal(str(txn["value"]))
        cost = Decimal(str(txn["cost"]))
        price = Decimal(str(txn["price"]))
        fee = Decimal(str(txn["fee"]))
        stock_symbol = txn["symbol"]
        date = txn["date"]

        if txn_type == "Buy":
            buys.append({
                "units": units,
                "cost": cost,
                "price": price,
                "fee": fee,
                "date": date
            })

        elif txn_type == "Sell":
            remaining_units_to_match = units
            total_cost_basis = Decimal('0.0')

            while remaining_units_to_match > 0 and buys:
                buy = buys[0]
                available_units = buy["units"]

                if available_units <= remaining_units_to_match:
                    # Fully use this buy
                    cost_basis = buy["cost"]
                    total_cost_basis += cost_basis
                    remaining_units_to_match -= available_units
                    buys.popleft()
                else:
                    # Partially use this buy
                    proportion = remaining_units_to_match / available_units
                    cost_basis = buy["cost"] * proportion
                    total_cost_basis += cost_basis
                    buy["units"] -= remaining_units_to_match
                    buy["cost"] -= cost_basis
                    remaining_units_to_match = Decimal('0.0')

            proceeds = value - fee
            capital_gain_loss = proceeds - total_cost_basis

            results.append({
                "symbol": stock_symbol,
                "date": date,
                "units_sold": units,
                "proceeds": float(proceeds),
                "cost_basis": float(total_cost_basis),
                "capital_gain_loss": float(capital_gain_loss),
            })

    return results
