from pathlib import Path

PORTFOLIO_FILE = Path('portfolio.json')

INDUSTRY_GROUPS = {
    'AI / Software': {
        'Palantir': 'PLTR',
        'Snowflake': 'SNOW',
        'C3.ai': 'AI',
        'BigBear.ai': 'BBAI',
        'SoundHound AI': 'SOUN',
    },
    'Semiconductors / Chips': {
        'NVIDIA': 'NVDA',
        'AMD': 'AMD',
        'Arm Holdings': 'ARM',
        'BrainChip': 'BRN.AX',
        'Weebit Nano': 'WBT.AX',
        'Archer Materials': 'AXE.AX',
    },
    'Biotech / Gene Editing': {
        'CRISPR Therapeutics': 'CRSP',
        'Intellia Therapeutics': 'NTLA',
        'Editas Medicine': 'EDIT',
        'Beam Therapeutics': 'BEAM',
    },
    'Space / Satellite': {
        'Rocket Lab': 'RKLB',
        'AST SpaceMobile': 'ASTS',
    },
    'Defense / Drone': {
        'DroneShield': 'DRO.AX',
        'Elsight': 'ELS.AX',
    },
    'Battery / Energy': {
        'Novonix': 'NVX.AX',
        'Altech Batteries': 'ATC.AX',
        'Arafura Rare Earths': 'ARU.AX',
        'Ionic Rare Earths': 'IXR.AX',
        'Lake Resources': 'LKE.AX',
        'Sayona Mining': 'SYA.AX',
        '88 Energy': '88E.AX',
        'Invictus Energy': 'IVZ.AX',
        'ChargePoint': 'CHPT',
        'Blink Charging': 'BLNK',
        'Workhorse Group': 'WKHS',
    },
    'Big Players': {
        'Microsoft': 'MSFT',
        'Alphabet (Google)': 'GOOGL',
        'Meta': 'META',
        'Amazon': 'AMZN',
        'NVIDIA': 'NVDA',
    },
    'Long-Term ETFs': {
        'Vanguard Diversified High Growth ETF': 'VDHG.AX',
        'Vanguard Australian Shares ETF': 'VAS.AX',
        'Vanguard International Shares ETF': 'VGS.AX',
    },
    'Crypto': {
        'Bitcoin': 'BTC-AUD',
        'Ethereum': 'ETH-AUD',
        'XRP': 'XRP-AUD',
        'Solana': 'SOL-AUD',
    },
}

IPO_RADAR = [
    {'Company': 'SpaceX', 'Theme': 'Space', 'Status': 'Private / Watch'},
    {'Company': 'Anthropic', 'Theme': 'AI', 'Status': 'Private / Watch'},
    {'Company': 'OpenAI', 'Theme': 'AI', 'Status': 'Private / Watch'},
    {'Company': 'Databricks', 'Theme': 'AI Data', 'Status': 'Private / Watch'},
    {'Company': 'Scale AI', 'Theme': 'AI Infrastructure', 'Status': 'Private / Watch'},
]
