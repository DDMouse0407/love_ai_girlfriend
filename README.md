# Love AI Girlfriend

This project is a LINE chatbot implemented with FastAPI. It integrates
with the ECPay payment gateway so users can purchase plans and have
their membership time extended automatically.

## ECPay callback configuration

1. Set the environment variables `ECPAY_MERCHANT_ID`, `ECPAY_HASH_KEY` and
   `ECPAY_HASH_IV` in your deployment environment.
2. In the ECPay merchant console, configure the store's **Server Reply URL**
   (also known as `ReturnURL`) to point to:
   `https://<your-domain>/payment_callback`.
3. When you generate purchase links for users, include their LINE user ID in
   `CustomField1`. The callback endpoint uses this value to identify which
   user made the purchase.
4. `TradeAmt` sent by ECPay is mapped to plans in `main.py` via the `PLANS`
   dictionary. The corresponding number of days will be added to the
   user's `paid_until` date upon a successful callback.

With the above configuration, once a customer completes payment through
ECPay, the server will receive the callback and update the database
accordingly.
