#!/usr/bin/env python
"""Monitor bank PDFs and send AI summaries of changes to Telegram."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime
import filecmp
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from google import genai
import pandas as pd
from PyPDF2 import PdfReader
import requests

BASE_DIR = Path(__file__).resolve().parent
PDF_DIR = BASE_DIR / "PDF Files"
SCHEDULER_FILE = BASE_DIR / "scheduler.txt"
CONFIG_FILE = BASE_DIR / "CC_Name_URL.xlsx"
load_dotenv(BASE_DIR / ".env")
ai_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
client = None


def compare_and_summarize_with_gemini(original_text, new_text):
    """Summarize substantive changes between two document versions."""
    if not client:
        return "ERROR: Gemini client not initialized. Cannot summarize changes."

    prompt = (
        "You are an AI financial credit card document analyst. "
        "Your task is to compare two versions of a bank's terms and conditions. "
        "Analyze the OLD TERMS and the NEW TERMS. "
        "Provide a CONCISE bullet-point summary of all substantive changes, "
        "such as changes to *fees*, *interest rates*, *cashback rewards*,*miles rewards*, *eligibility*, or *exclusion* clauses. "
        "Organize the changes in point form without asterisks or text formatting. "
        "If it is relating to formatting or minor grammatical changes, just answer 'Document format updates. No change to T&C'. "
        "\n\n--- OLD TERMS ---\n"
        f"{original_text[:10000]} " # Truncate to save tokens
        "\n\n--- NEW TERMS ---\n"
        f"{new_text[:10000]} " # Truncate to save tokens
    )

    try:
        response = client.models.generate_content(
            model=ai_model,
            contents=prompt
        )
        return response.text or "ERROR: Gemini returned an empty summary."
    except Exception as exc:
        print(f"Gemini summary failed ({type(exc).__name__}).")
        return "ERROR: Failed to get summary from Gemini API."


def extract_text(path):
    with path.open("rb") as pdf:
        return "".join(page.extract_text() or "" for page in PdfReader(pdf).pages)


def send_telegram(message):
    """Split long alerts and verify delivery before replacing the original."""
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    for start in range(0, len(message), 2000):
        with requests.post(url, json={
            "chat_id": os.environ["TELEGRAM_CHAT_ID"],
            "text": message[start:start + 2000],
        }, timeout=30) as response:
            response.raise_for_status()
            if not response.json().get("ok"):
                raise RuntimeError("Telegram rejected the notification.")


def download_pdf(pdf_url, path, session):
    try:
        with session.get(pdf_url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with path.open("wb") as pdf:
                for chunk in response.iter_content(chunk_size=65536):
                    pdf.write(chunk)
        # A successful HTTP response may contain an error page or broken PDF.
        with path.open("rb") as pdf:
            reader = PdfReader(pdf)
            if reader.is_encrypted or not len(reader.pages):
                raise ValueError("Downloaded PDF is encrypted or has no pages.")
    except Exception as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        reason = f"HTTP {status}" if status is not None else type(exc).__name__
        print(f"ERROR: PDF download failed ({reason}).")
        try:
            send_telegram(
                f"ERROR: Unable to download a usable PDF.\n"
                f"Source URL: {pdf_url}\n"
                f"Reason: {reason}\n"
                "Any previously saved original has been kept."
            )
        except Exception as notification_error:
            # Never print HTTP exception text: Telegram URLs contain the token.
            print(f"ERROR: Telegram error alert failed ({type(notification_error).__name__}).")
        raise


def card(pdf_url, downloaded_file_name, downloaded_path):
    """Replace the original only after successful processing and notification."""
    name = Path(downloaded_file_name).name
    original = PDF_DIR / f"{Path(name).stem}_original.pdf"
    filecmp.clear_cache()
    if original.exists() and filecmp.cmp(downloaded_path, original, shallow=False):
        print(f"No Changes found in {name}.")
        return
    new_text = extract_text(downloaded_path)
    if not original.exists():
        downloaded_path.replace(original)
        print(f"Original file not found for {name}. Saving current as original.")
        return
    old_text = extract_text(original)
    if old_text == new_text:
        print(f"No Changes found in {name}.")
        return
    print(f"Changes found in {name}. Sending notification.")
    summary = compare_and_summarize_with_gemini(old_text, new_text)
    send_telegram(
        f"Terms and Conditions Updated for {name}!\n"
        f"Source URL: {pdf_url}\n\n"
        f"Summary of Changes by {ai_model}:\n{summary}"
    )
    downloaded_path.replace(original)


def run_script():
    cards = pd.read_excel(CONFIG_FILE)
    jobs = list(cards[["PDF File Name", "URL"]].itertuples(index=False, name=None))
    workers = max(1, min(8, int(os.getenv("PDF_DOWNLOAD_WORKERS", "4"))))
    PDF_DIR.mkdir(exist_ok=True)
    failed_downloads = 0
    with ExitStack() as stack:
        temporary = Path(stack.enter_context(TemporaryDirectory(dir=PDF_DIR)))
        sessions = [stack.enter_context(requests.Session()) for _ in range(workers)]
        # ExitStack waits for workers before closing sessions and removing files.
        pool = stack.enter_context(ThreadPoolExecutor(max_workers=workers))
        for start in range(0, len(jobs), workers):
            batch = jobs[start:start + workers]
            paths = [temporary / f"{i}.download" for i in range(len(batch))]
            downloads = [
                pool.submit(download_pdf, url, path, session)
                for (_, url), path, session in zip(batch, paths, sessions)
            ]
            # Keep comparisons and change notifications in spreadsheet order.
            for (name, url), path, future in zip(batch, paths, downloads):
                try:
                    future.result()
                except Exception:
                    failed_downloads += 1  # download_pdf already attempted an alert.
                    continue
                card(url, name, path)
                path.unlink(missing_ok=True)
    if failed_downloads:
        # Leave the scheduler unchanged so a partial run can be retried today.
        raise RuntimeError(f"{failed_downloads} PDF download(s) failed.")


def scheduler_update():
    with SCHEDULER_FILE.open("a", encoding="utf-8") as scheduler:
        scheduler.write(f"file last updated at {datetime.now():%d/%m/%Y %H:%M:%S}\n")


def main():
    global client
    today = datetime.now().strftime("%d/%m/%Y")
    if SCHEDULER_FILE.exists() and today in SCHEDULER_FILE.read_text(encoding="utf-8"):
        print("Script has already been run today. Exiting.")
        return
    if not CONFIG_FILE.exists():
        # The top-level handler hides exception messages, so explain the fix here.
        print(f"Missing {CONFIG_FILE.name}. Copy CC_Name_URL.example.xlsx to {CONFIG_FILE.name} and add your cards.", file=sys.stderr)
        sys.exit(1)
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not os.getenv(key):
            raise ValueError(f"Missing required environment variable: {key}")
    try:
        client = genai.Client()
        print("Gemini client initialized successfully.")
    except Exception as exc:
        print(f"Error initializing Gemini client ({type(exc).__name__}).")
    run_script()
    scheduler_update()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # HTTP exceptions can include the Telegram token in the request URL.
        # Do not print exception messages or tracebacks in routine run logs.
        print(f"Run failed ({type(exc).__name__}). Check local configuration and service availability.", file=sys.stderr)
        sys.exit(1)
