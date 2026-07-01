# Stripe Production Launch Checklist

Going live with Stripe is straightforward, but it requires carefully duplicating your Test Mode configuration into Live Mode. When you are ready to launch Novena Hub to real paying customers, follow this step-by-step mental framework.

> [!IMPORTANT]  
> Test mode and Live mode in Stripe are completely isolated. None of your test products, pricing tables, or settings carry over automatically. You must recreate them in Live mode.

## 1. Recreate Your Billing Structure in Live Mode
1. **Toggle to Live Mode:** In your Stripe Dashboard, toggle the switch in the top right from "Test Mode" to "Live Mode".
2. **Recreate Products:** Go to the Product Catalog and recreate the **Starter**, **Business**, and **Enterprise** plans with their exact names, descriptions, and recurring prices.
3. **Recreate the Pricing Table:** Go to the Pricing Table section and create a new pricing table using your new Live products. Copy the new Pricing Table ID (it starts with `prctbl_...`).

## 2. Configure the Live Customer Portal
1. Go to **Settings > Billing > Customer Portal**.
2. Make sure you are in Live Mode.
3. Customize the branding, add your Terms of Service and Privacy Policy links, and enable the features you want customers to have (e.g., updating payment methods, viewing invoice history).
4. Save the configuration.

## 3. Configure Your Live Webhook
Instead of using the Stripe CLI to forward webhooks to your local machine, you need to point Stripe to your actual production server.
1. In the Stripe Dashboard, go to **Developers > Webhooks**.
2. Click **Add an endpoint**.
3. Set the Endpoint URL to your live domain: `https://[your-production-domain.com]/stripe/webhook/`
4. Select the events to listen to. At a minimum, select:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. Save the endpoint and copy the **Webhook Signing Secret** (it starts with `whsec_...`).

## 4. Update Your Codebase & Environment Variables
Before deploying to your live server, you need to update a few hardcoded values and environment variables.

### Update Product IDs in `metadata.py`
In `apps/subscriptions/metadata.py`, we currently have test product IDs hardcoded (e.g., `stripe_id="prod_UiHJ..."`). 
> [!WARNING]  
> You must replace these with the new **Live Product IDs** you generated in Step 1.

### Production Environment Variables (`.env`)
On your live production server, ensure the following environment variables are set:

```env
# 1. Enable Live Mode
STRIPE_LIVE_MODE=True

# 2. Add your Live API Keys (from Stripe Developers -> API Keys)
STRIPE_LIVE_PUBLIC_KEY=pk_live_...
STRIPE_LIVE_SECRET_KEY=sk_live_...

# 3. Add your Live Webhook Secret (from Step 3)
STRIPE_LIVE_WEBHOOK_SECRET=whsec_...

# 4. Add your Live Pricing Table ID (from Step 1)
STRIPE_PRICING_TABLE_ID=prctbl_...
```

## 5. Sync the Production Database
Once your code is deployed to the production server and the `.env` variables are loaded, you need to pull the live Stripe data into your production database. Run this command on your live server:

```bash
python manage.py djstripe_sync_models
```

## 6. Perform a Final Live Test
Before announcing the launch:
1. Create a 100% off coupon code in the live Stripe dashboard.
2. Register a new account on your production site.
3. Go through the checkout process using a real credit card, but apply the coupon code so you aren't charged.
4. Verify that the subscription activates properly and the webhooks are received without errors.
