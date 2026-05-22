# Live Integrations Setup

This guide finishes the two external integrations that Rayzaa cannot self-provision:

- `Razorpay Test Mode` for the live payment trigger
- `Telegram` for operational alerts

Use only the authoritative workspace:

- `C:\Projects\Rayzaa`

## What Rayzaa Already Does

Rayzaa already contains:

- server-side Razorpay order creation
- checkout callback signature verification
- webhook signature verification
- webhook normalization into `TransactionEvent`
- post-persistence Telegram alert dispatch

The missing work is only configuration and provider dashboard setup.

## 1. Create Local Integration Config

Copy:

- `config\local.env.ps1.example`

to:

- `config\local.env.ps1`

Then fill the real values.

## 2. Razorpay Setup

In Razorpay:

1. Create or open your account.
2. Use `Test Mode`.
3. Get:
   - `Key ID`
   - `Key Secret`
4. Create a webhook secret for Rayzaa.
5. Configure the webhook URL:

```text
https://YOUR_PUBLIC_API_HOST/api/integrations/razorpay/webhook
```

6. Subscribe to:
   - `payment.captured`

Rayzaa currently expects:

- `RAYZAA_RAZORPAY_WEBHOOK_EVENT=payment.captured`

To print the exact values Rayzaa expects for the Razorpay dashboard:

```powershell
cd C:\Projects\Rayzaa
.\scripts\show_razorpay_webhook_setup.ps1 -WorkspaceRoot C:\Projects\Rayzaa
```

## 3. Telegram Setup

In Telegram:

1. Create a bot with `@BotFather`.
2. Save the bot token.
3. Start a chat with the bot or add it to a group.
4. Send one message manually.
5. Find the `chat_id`.
6. If using forum topics, also capture `message_thread_id`.

Put these into `config\local.env.ps1`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_MESSAGE_THREAD_ID` optional

To discover the actual `chat_id` after messaging the bot:

```powershell
cd C:\Projects\Rayzaa
.\scripts\get_telegram_chat_id.ps1 -WorkspaceRoot C:\Projects\Rayzaa
```

## 4. Public Webhook Requirement

Razorpay webhooks need a public HTTPS backend URL.

For local demo use, that usually means:

- deployed backend on Render / Railway / Fly
or
- an HTTPS tunnel to your local backend

Then set:

- `RAYZAA_PUBLIC_API_URL`

to that public HTTPS base URL.

## 5. Readiness Check

Run:

```powershell
cd C:\Projects\Rayzaa
.\scripts\check_live_integrations.ps1 -WorkspaceRoot C:\Projects\Rayzaa -Mode demo
```

This will tell you:

- which credentials are loaded
- whether the webhook URL is formed correctly
- whether you are still missing Razorpay or Telegram setup
- whether the running backend reports the integrations as configured

## 6. Demo Startup

Once the readiness check is clean, run:

```powershell
cd C:\Projects\Rayzaa
.\scripts\start_demo.ps1 -WorkspaceRoot C:\Projects\Rayzaa
```

`start_demo.ps1` now auto-loads:

- `config\local.env.ps1`

if it exists in the authoritative workspace.

## 7. What You Still Must Do Manually

Rayzaa cannot do these provider actions for you:

1. create the Razorpay test account / fetch test keys
2. create the Razorpay webhook in the dashboard
3. create the Telegram bot with `@BotFather`
4. obtain the Telegram `chat_id`
5. provide a public HTTPS API URL for the webhook

Everything else is already implemented in the Rayzaa codebase.
