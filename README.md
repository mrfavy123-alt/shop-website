# Zamac Füds

A restaurant storefront for Nigerian and continental meals, pastries, small chops, and catering. The homepage includes product details, search and category filters, an editable cart, light/dark mode, Google sign-in for checkout, booking and training enquiry forms, a contact form, and an order confirmation screen.

## Supabase setup

1. Run [`supabase_schema.sql`](supabase_schema.sql) in the Supabase SQL editor. It creates and seeds `users`, `products`, `cart_items`, `orders`, `order_items`, `bookings`, `training_programs`, `training_enrollments`, `training_payments`, and `contact_messages`, plus the transactional order and enrollment functions.
2. Enable Email and Google under Supabase Authentication providers. Email/password sign-in and account creation appear at checkout; if email confirmation is enabled, new customers confirm their address before signing in. Add your local and deployed website URLs to the redirect allowlist. Create a Google OAuth web client and register your site origins plus the callback URL shown on the Supabase Google provider page.
3. Copy `.env.example` to `.env`, then set the Supabase URL, publishable key, server-only secret key, and Mailgun domain/API key/sender. Add your Paystack secret key to enable training instalments; begin with a Paystack test key. Set `PUBLIC_BASE_URL` to the deployed HTTPS URL for production. Do not put any server secret in browser code.
4. Install Node.js 24 from [nodejs.org](https://nodejs.org/) if it is not already installed. Copy `.env.example` to `.env` and fill in the Supabase values. Start the shop:

   ```sh
   npm start
   ```

5. Open http://localhost:8000. The Node.js server serves the website and its `/api` routes together.

## Deploying to Vercel

The `api/` directory contains Node.js functions for the shop API. `package.json` selects Node.js 24 for Vercel deployments. Vercel provides that runtime during deployment. Vercel function storage is temporary, so configure Supabase before using the forms or checkout.

1. Run [`supabase_schema.sql`](supabase_schema.sql) in the Supabase SQL editor if you have not already.
2. In Vercel, open **Project Settings → Environment Variables** and add `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY` from the Supabase project. Add `PAYSTACK_SECRET_KEY` to enable instalment payments, and the Mailgun variables if you want order confirmation emails.
3. Redeploy the Vercel project so it builds the Node.js functions and loads the environment variables.

The local SQLite database is not used by the Node.js server or Vercel functions.

Orders use Supabase's catalog prices and are saved with their item snapshots in one database transaction. Mailgun runs after that commit. Booking requests, contact messages, course enrollments, and two scheduled training instalments are saved to their own tables. When Paystack is configured, each training instalment uses a separate hosted payment and the server verifies its reference and amount before marking it paid. Without a Paystack key, the enrollment request is still saved and no payment is charged. The course and materials prices shown in the demo are sample prices to replace with approved fees.

Google login, form submissions, orders, and training payments require the Supabase configuration above.
# shop-website
# shop-website
