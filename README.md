# PyFinBot
[![Build Status](https://github.com/GreenMachine582/PyFinBot/actions/workflows/general_tests.yml/badge.svg?branch=main)](https://github.com/GreenMachine582/PyFinBot/actions/workflows/project_tests.yml)
![Python version](https://img.shields.io/badge/python-3.10%20--%203.12-blue.svg)
![GitHub release](https://img.shields.io/github/v/release/GreenMachine582/PyFinBot?include_prereleases)

## Table of Contents
- [Introduction](#introduction)
- [Key Features](#-key-features)
- [Planned Milestones](#-planned-milestones)
- [Testing](#testing)
- [License](#license)

---

## Introduction
PyFinBot is a lightweight, extensible financial tracking tool built in Python, designed to help users manage and 
analyze their stock trading activity. By leveraging relational database design and SQL-based reporting, PyFinBot 
offers precise insights into holdings, transaction history, and capital gains or losses per financial year. Ideal for 
personal investors or hobbyist traders, it serves as a transparent and customizable alternative to spreadsheet-based 
tracking.

## 🚀 Key Features
* 📊 Transaction Recording: Track Buy/Sell orders with support for fees, prices, values, and financial year grouping.
* 📆 Holdings Snapshot: Query real-time or historical stock units held as of any given date. 
* 💰 Capital Gain/Loss Calculation: Determine net gains/losses per stock by financial year using average cost basis.
* 🔗 Relational Database Design: Clean, normalized schema to ensure data integrity and efficient queries.
* 🔐 Multi-user Support (optional): Track transactions per user if needed.
* 📦 Modular Architecture: Built to be extended with additional features like tax reports, visualizations, or API integration.

## 🎯 Planned Milestones
1. ✅ MVP – Schema design, basic transaction insertion, and SQL-based queries.
2. 🔄 Import System – CSV or Excel import of stock transactions.
3. 📈 Reporting Module – Generate FY-based reports for holdings and capital gains.
4. 🧮 FIFO Method Support – Accurate gain/loss computation based on FIFO accounting.
5. 🌐 CLI Interface – Interact via command line with exportable summaries.
6. 🖥️ Web Dashboard (optional) – View and interact with data through a simple Flask or Django front end.

## Testing
PyFinBot includes a comprehensive suite of unit tests to ensure the reliability and stability of its features. Tests 
cover various aspects of the core functionality.

### Running Tests
To run the tests, navigate to the project root directory and execute the following command:

```bash
python -m unittest discover -s tests
```

## License
PyFinBot is licensed under the MIT License, see [LICENSE](LICENSE) for more information.