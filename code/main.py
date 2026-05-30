import argparse
import asyncio
import pandas as pd
import logging
import os
import sys
import traceback

from agent import app
from schema import SupportTicket
from tools import init_retriever

# Determine the correct log path based on the AGENTS.md rules
if sys.platform.startswith('win'):
    LOG_PATH = os.path.join(os.environ.get('USERPROFILE', ''), 'hackerrank_orchestrate', 'log.txt')
else:
    LOG_PATH = os.path.join(os.environ.get('HOME', ''), 'hackerrank_orchestrate', 'log.txt')

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

async def process_ticket(index: int, row: pd.Series) -> dict:
    """Process a single ticket asynchronously."""
    ticket = SupportTicket(
        issue=str(row.get('Issue', '')),
        subject=str(row.get('Subject', '')),
        company=str(row.get('Company', 'None'))
    )

    logging.info(f"--- Processing ticket {index + 1}: [{ticket.company}] {ticket.subject[:60]} ---")

    initial_state = {
        "ticket": ticket,
        "messages": [],
        "triage_decision": "PENDING",
        "request_type": "invalid",
        "product_area": "unknown"
    }

    try:
        result = await app.ainvoke(initial_state)
        final_output = result.get("final_output")

        if final_output:
            logging.info(f"[OK] Ticket {index + 1} done. Status: {final_output.status} | Type: {final_output.request_type} | Area: {final_output.product_area}")
            return {
                "status": final_output.status,
                "product_area": final_output.product_area,
                "response": final_output.response,
                "justification": final_output.justification,
                "request_type": final_output.request_type
            }
        else:
            logging.error(f"[FAIL] Ticket {index + 1}: No final output returned from agent.")
            return get_fallback_output("MissingFinalOutput")
    except Exception as e:
        error_name = type(e).__name__
        logging.error(f"[FAIL] Ticket {index + 1} exception: {error_name}: {e}")
        logging.error(traceback.format_exc())
        return get_fallback_output(error_name)


def get_fallback_output(error_type: str = "UnknownError"):
    return {
        "status": "failed",
        "product_area": "system",
        "response": "I am unable to process this request at the moment due to a technical error. Our engineering team has been notified.",
        "justification": f"SYSTEM_FAILURE: {error_type}. Processing aborted to prevent further errors.",
        "request_type": "product_issue"
    }


async def process_dataframe(df, batch_size=10, delay_seconds=65):
    """
    Process the dataframe efficiently using a Semaphore for concurrency.
    
    Instead of waiting for an entire batch to finish, this uses a Semaphore to 
    maintain a constant number of active workers. A small stagger delay is added
    to avoid hitting 'burst' rate limits.
    """
    semaphore = asyncio.Semaphore(batch_size)
    all_results = [None] * len(df)
    
    # Calculate a smooth stagger delay. 
    # If the user wants 10 tickets every 65 seconds, that's roughly 6.5s per ticket.
    # We'll use a smaller stagger to allow concurrency while spreading the load.
    stagger = delay_seconds / batch_size if batch_size > 0 else 0
    
    async def worker(idx, row):
        async with semaphore:
            try:
                result = await process_ticket(idx, row)
                all_results[idx] = result
            except Exception as e:
                logging.error(f"[FAIL] Unexpected error in worker for ticket {idx + 1}: {e}")
                all_results[idx] = get_fallback_output()

    logging.info(f"[INFO] Starting processing with concurrency={batch_size} and stagger={stagger:.2f}s")
    
    tasks = []
    for idx, row in df.iterrows():
        task = asyncio.create_task(worker(idx, row))
        tasks.append(task)
        if stagger > 0:
            await asyncio.sleep(stagger)
            
    await asyncio.gather(*tasks)
    return all_results


def main():
    parser = argparse.ArgumentParser(description="HackerRank Orchestrate Support Agent")
    parser.add_argument("--input", type=str, required=True, help="Path to input CSV")
    parser.add_argument("--output", type=str, default="../support_tickets/output.csv", help="Path to output CSV")
    parser.add_argument("--batch_size", type=int, default=10, help="Number of tickets to process in one batch")
    parser.add_argument("--delay", type=int, default=65, help="Seconds to sleep between batches")
    args = parser.parse_args()

    logging.info(f"Starting agent processing on {args.input}")

    # Pre-load embedding model and vector store
    logging.info("Warming up the RAG engine (loading embeddings)...")
    init_retriever()

    try:
        df = pd.read_csv(args.input)
    except Exception as e:
        logging.error(f"Failed to read input CSV: {e}")
        return

    logging.info(f"Loaded {len(df)} tickets from {args.input}")

    # Process tickets asynchronously in batches
    results = asyncio.run(process_dataframe(df, batch_size=args.batch_size, delay_seconds=args.delay))

    # Save final aggregated results
    output_df = pd.DataFrame(results)
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    output_df.to_csv(args.output, index=False)

    logging.info(f"Finished processing {len(df)} tickets. Output saved to {args.output}")


if __name__ == "__main__":
    main()
