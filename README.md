# Credit Card Terms & Conditions Change Tracker

An automated monitoring system that detects changes to credit card Terms & Conditions (T&C), generates AI-powered summaries of the differences, and sends real-time notifications to a Telegram channel.

The project is designed to help users stay informed whenever banks update their credit card terms and conditions, ensuring they never miss important changes that could affect rewards, cashback, fees, or eligibility.

---

## Local setup

Use Python 3.10 or newer. From this folder in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item CC_Name_URL.example.xlsx CC_Name_URL.xlsx
```

Fill in `.env` locally with your Gemini API key, Telegram bot token, and target
chat ID. Choose a Gemini model available to your account. Replace the sample
rows in `CC_Name_URL.xlsx` with the cards you want to monitor. Run
`.venv\Scripts\python CC_PDF_WTS.py` or `CC_PDF_New.bat`.
The script sends Telegram notifications when document changes are detected.

## Public repository privacy

Keep `.env`, downloaded PDFs, logs, and runtime files local; `.gitignore`
excludes them from normal Git additions. Never force-add these files. Only
`.env.example` with empty credentials belongs in the repository.

Your card list, `CC_Name_URL.xlsx`, is also kept local because it shows which
cards you track. Only `CC_Name_URL.example.xlsx` with sample rows is
published. Its required columns are `PDF File Name` and `URL`.

Document excerpts are sent to Gemini for analysis. Change summaries and source
URLs are sent to the configured Telegram chat. Use public documents and a chat
you control. AI summaries may omit changes; consult the original documents.

Before publishing a fork, review both tracked files and Git history. Ignore
rules do not remove earlier commits. Excel stores the author name and the
file's folder path inside `.xlsx` files; remove them with File > Info > Check
for Issues > Inspect Document. Configure your Git host's private/noreply commit
email before your first commit.

If a credential is ever committed or published, revoke/rotate it with its
provider before removing it from history. Do not paste tokens or full HTTP
tracebacks into public issues. The command-line runner reports error types
without printing URLs that may contain credentials.

## Features

* Monitor multiple credit card Terms & Conditions documents
* Automatically download the latest T&C PDFs
* Compare the latest document against the previously stored version
* Generate AI-powered summaries of detected changes
* Send instant notifications to a Telegram channel
* Fully automated through Windows Task Scheduler (or any scheduled job)
* Keep a record of its last run so that it will not run again for the day

---

## How It Works

1. A scheduled task (Windows Task Scheduler in this project) automatically runs the Python script at a predefined interval.

2. The script reads an Excel (`.xlsx`) configuration file containing:

   * Credit card names
   * Corresponding Terms & Conditions PDF URLs

3. For each configured credit card:

   * Download the latest Terms & Conditions PDF.
   * Compare it with the previously archived version stored in the local repository.

4. If no changes are detected:

   * The script moves on to the next credit card.

5. If changes are detected:

   * The updated document replaces the previous version.
   * Gemini Flash 3.1 Lite analyzes both versions.
   * An AI-generated summary highlights the key differences.

6. A notification containing the summarized changes is sent directly to a Telegram channel.
   
7. Once the run finishes, it will log down the datetime it last run in a simple text file. The script will also check if it has run for the day and if it did, it will not run again.

---

## Why This Project?

Banks periodically revise their credit card Terms & Conditions without drawing much attention to the specific changes. These updates can affect:

* Cashback eligibility
* Reward point accumulation
* Travel benefits
* Promotional offers
* Spending requirements
* Fees and charges

Instead of manually reviewing lengthy PDF documents, this project automatically detects modifications and provides concise summaries, making it easy to stay informed with minimal effort.

---

## Tech Stack

| Technology                              | Purpose                                    |
| --------------------------------------- | ------------------------------------------ |
| **Python**                              | Core automation and processing             |
| **openpyxl / pandas**                   | Read Excel configuration                   |
| **PDF Comparison using PyPDF2**         | Detect changes between document versions   |
| **Gemini Flash 3.1 Lite**               | AI-generated summaries of document changes |
| **Telegram Bot API**                    | Send notifications to Telegram             |
| **Windows Task Scheduler**              | Schedule automatic execution               |

### Why Gemini Flash 3.1 Lite?

Gemini Flash 3.1 Lite provides fast response times and a generous free usage tier while producing concise, high-quality summaries of document changes, making it well suited for this use case.

---

## Workflow

```text
┌──────────────────────────┐
│ Windows Task Scheduler   │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Execute Python Script    │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Read Excel Configuration │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Download Latest T&C PDF  │
└─────────────┬────────────┘
              │
              ▼
┌──────────────────────────┐
│ Compare with Repository  │
└───────┬───────────┬──────┘
        │           │
   No Changes   Changes Found
        │           │
        ▼           ▼
     Continue   AI Summarizes
                    │
                    ▼
          Send Telegram Alert
```

---

## Configuration

The application reads `CC_Name_URL.xlsx` (copied from
`CC_Name_URL.example.xlsx`) with the following format:

| PDF File Name | URL |
| ----------- | ------------------------------ |
| card-a.pdf  | https://example.com/card-a.pdf |
| card-b.pdf  | https://example.com/card-b.pdf |

Each row represents one credit card to monitor.

---

## Notification Example

```text
'Terms and Conditions Updated for ABC_credit_card.pdf

Summary of Changes by gemini-3.1-flash-lite:

Changes Summary:
• Cashback rate updated for dining transactions.
• Minimum monthly spending increased from $500 to $800.
• New exclusions added for digital wallet transactions.

```

---

## Future Improvements

* Track historical versions of every T&C document
* Scheduled cloud deployment (GitHub Actions, Azure, AWS, etc.)

## Download errors

Failed HTTP requests, timeouts, empty responses, and invalid or encrypted PDFs
trigger a Telegram error alert with the source URL and error type/status.
The saved original is preserved and remaining downloads continue. A run with
failed downloads exits unsuccessfully and is not recorded as completed, so it
can be retried the same day. Temporary downloads are cleaned up. If Telegram
itself is unavailable, the alert failure is reported locally without exposing
the bot token; delivery cannot be guaranteed during an outage.
