# Bond Portfolio Dashboard

## Overview
The **Bond Portfolio Dashboard** is a Streamlit-based web application designed to help users analyze and manage their bond portfolios. The dashboard allows users to upload bond portfolio data in CSV format, calculate key financial metrics, and visualize the impact of changes in Yield to Maturity (YTM) on the portfolio's gain/loss.

---

## Features

1. **File Upload**:
   - Upload your bond portfolio in CSV format.
   - The application supports flexible column mapping to handle variations in column names (e.g., case sensitivity, extra spaces).

2. **Data Cleaning**:
   - Automatically standardizes column names to ensure compatibility with the application.
   - Validates the presence of required columns and provides error messages if any are missing.

3. **Key Calculations**:
   - **Initial Investment Value**: Calculates the initial cost of each bond based on its price and face value.
   - **Book Value**: Computes the amortized value of the bond up to the current date.
   - **Market Value**: Determines the current market value of the bond based on the yield to maturity (YTM).
   - **Gain/Loss**: Calculates the difference between the market value and the book value.

4. **Dynamic Yield Adjustment**:
   - Users can input a new YTM value to see how it impacts the bond's gain or loss.

5. **Data Visualization**:
   - Displays the uploaded and processed portfolio data in an interactive table.
   - Provides insights into the portfolio's performance and the impact of yield changes.

---

## How It Works

1. **Upload Your Portfolio**:
   - Prepare a CSV file with the following columns:
     - `Purchased Date`: The date the bond was purchased.
     - `Maturity Date`: The date the bond matures.
     - `Purchased YTM`: The yield to maturity at the time of purchase.
     - `Coupon`: The annual coupon rate of the bond.
     - `Face Value`: The face value of the bond.
     - `Initial Inv Value`: The initial investment value of the bond.
     - `Book Value`: The amortized value of the bond up to the current date.

2. **Flexible Column Mapping**:
   - The application automatically maps column names in your CSV file to the expected names, even if they have extra spaces, different capitalization, or slight variations.

3. **Dynamic Yield Adjustment**:
   - Enter a new YTM value in the input field to calculate the impact on the bond's gain or loss.
   - The application recalculates the market value and gain/loss for each bond based on the new YTM.

4. **View Results**:
   - The dashboard displays the updated portfolio with the recalculated gain/loss.
   - Users can analyze the impact of yield changes on their bond portfolio.

---

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd bond-portfolio-dashboard
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   streamlit run bond_dashboard.py
   ```

---

## Requirements

- Python 3.8+
- Required Python packages (listed in `requirements.txt`):
  - `streamlit`
  - `pandas`
  - `numpy`
  - `numpy-financial`

---

## Folder Structure
```
portfolio/
│
├── bond_dashboard.py       # Main Streamlit application
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore file
├── README.md               # Project documentation
```

---

## License
This project is licensed under the MIT License. See the LICENSE file for details.

---