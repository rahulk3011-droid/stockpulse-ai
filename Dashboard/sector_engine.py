GICS_GROUPS = {
    "Information Technology": {
        "Microsoft": "MSFT",
        "Apple": "AAPL",
        "NVIDIA": "NVDA",
        "AMD": "AMD",
        "ASML": "ASML",
        "TSMC": "TSM",
        "WiseTech Global": "WTC.AX",
        "Xero": "XRO.AX",
    },
    "Health Care": {
        "Johnson & Johnson": "JNJ",
        "Pfizer": "PFE",
        "Moderna": "MRNA",
        "Vertex Pharma": "VRTX",
        "Regeneron": "REGN",
        "CSL": "CSL.AX",
        "ResMed": "RMD.AX",
    },
    "Financials": {
        "JPMorgan": "JPM",
        "Goldman Sachs": "GS",
        "Bank of America": "BAC",
        "Commonwealth Bank": "CBA.AX",
        "Westpac": "WBC.AX",
        "NAB": "NAB.AX",
        "ANZ": "ANZ.AX",
        "Vanguard Australian Shares ETF": "VAS.AX",
        "Vanguard International Shares ETF": "VGS.AX",
        "Vanguard Diversified High Growth ETF": "VDHG.AX",
    },
    "Consumer Discretionary": {
        "Tesla": "TSLA",
        "Amazon": "AMZN",
        "Nike": "NKE",
        "McDonalds": "MCD",
        "Aristocrat Leisure": "ALL.AX",
    },
    "Communication Services": {
        "Alphabet": "GOOGL",
        "Meta": "META",
        "Netflix": "NFLX",
        "Disney": "DIS",
        "Seek": "SEK.AX",
        "REA Group": "REA.AX",
    },
    "Industrials": {
        "Boeing": "BA",
        "Lockheed Martin": "LMT",
        "Raytheon": "RTX",
        "Caterpillar": "CAT",
        "Transurban": "TCL.AX",
        "Brambles": "BXB.AX",
    },
    "Consumer Staples": {
        "Coca-Cola": "KO",
        "Pepsi": "PEP",
        "Walmart": "WMT",
        "Coles": "COL.AX",
        "Woolworths": "WOW.AX",
    },
    "Energy": {
        "Exxon Mobil": "XOM",
        "Chevron": "CVX",
        "Woodside Energy": "WDS.AX",
        "Santos": "STO.AX",
        "Beach Energy": "BPT.AX",
    },
    "Materials": {
        "BHP": "BHP.AX",
        "Rio Tinto": "RIO.AX",
        "Freeport-McMoRan": "FCX",
        "Fortescue": "FMG.AX",
        "Newmont": "NEM",
    },
    "Real Estate": {
        "Prologis": "PLD",
        "Realty Income": "O",
        "Goodman Group": "GMG.AX",
        "Scentre Group": "SCG.AX",
    },
    "Utilities": {
        "NextEra Energy": "NEE",
        "Duke Energy": "DUK",
        "AGL Energy": "AGL.AX",
        "Origin Energy": "ORG.AX",
    },
}

def get_sector_stocks(sector_name: str):
    extra = {
        "Information Technology": {
            "ServiceNow": "NOW",
            "Snowflake": "SNOW",
            "Palantir": "PLTR",
        },
        "Energy": {
            "BP": "BP",
            "Shell": "SHEL",
        },
        "Materials": {
            "Alcoa": "AA",
        },
        "Communication Services": {
            "Telstra": "TLS.AX",
        },
        "Financials": {
            "Macquarie": "MQG.AX",
        },
    }
    return extra.get(sector_name, {})
