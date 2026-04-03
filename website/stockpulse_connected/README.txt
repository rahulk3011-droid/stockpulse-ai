Phase 2 Website Upgrade

What this phase adds:
- free vs paid access logic
- locked dashboard page for free users
- account page with plan visibility
- upgrade routes
- optional Stripe-ready checkout path
- local mock upgrade path for testing
- homepage FAQ and stronger conversion flow

How to use:
1. Back up your current website folder
2. Replace app.py
3. Replace templates folder
4. Replace static/style.css
5. Keep your existing app.db
6. Install/update requirements:
   pip install -r requirements.txt
7. Run:
   python app.py

Testing without Stripe:
- log in
- go to pricing
- click Pro or Premium
- mock upgrade will apply
