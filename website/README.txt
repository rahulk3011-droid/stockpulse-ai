<<<<<<< HEAD
StockPulse AI - Launch Optimized Website Package

Use this in the WEBSITE folder only.

Replace:
- app.py
- templates folder
- static/style.css
- requirements.txt
- .env.example if you want the updated example

Keep:
- app.db

After replacing:
1. Make sure your .env contains your real Stripe values
2. Install/update packages:
   pip install -r requirements.txt
3. Run Flask:
   python app.py

Optional Stripe webhook terminal:
stripe listen --forward-to http://127.0.0.1:5000/stripe/webhook
=======
StockPulse AI - Step 2 Premium UI Upgrade

Use these files in the WEBSITE folder only.

Replace:
- templates/home.html
- templates/pricing.html
- templates/account.html
- static/style.css

Keep:
- app.py
- app.db
- other templates unchanged
>>>>>>> a2263f5 (Added signup route)
