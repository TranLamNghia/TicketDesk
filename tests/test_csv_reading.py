from pathlib import Path
from sales import read_sales


def test_read_assets_sample_csv():
    # Trỏ đến file CSV trong assets/data/
    csv_file = Path(__file__).parent.parent / "assets" / "data" / "sample_sales.csv"
    sales = read_sales(csv_file)
    for item in sales:
        print(
            f"  - {item.product}: SL={item.quantity}, Giá={item.price:,.0f}, Thành tiền={item.total:,.0f}"
        )

    assert len(sales) > 0
    assert any(item.product == "Bút bi" for item in sales)
