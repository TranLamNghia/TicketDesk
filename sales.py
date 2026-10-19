import csv
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Sale:
    product: str
    quantity: int
    price: float

    @property
    def total(self) -> float:
        return self.price * self.quantity

def read_sales(path: Path) -> list[Sale]:
    sales: list[Sale] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                sale = Sale(
                    product = str(row["product"]),
                    quantity = int(row["quantity"]),
                    price = float(row["price"]),
                )
                sales.append(sale)
            except (KeyError, ValueError) as e:
                logger.warning("Skip row %s: %s", row, e)
                continue
    return sales



