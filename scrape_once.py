# scrape_once.py
from il_supermarket_scarper.scrapper_runner import MainScrapperRunner


def run(chain):
    runner = MainScrapperRunner(
        enabled_scrapers=[chain],
        dump_folder_name="dumps",
        multiprocessing=1
    )
    runner.run(when_date="latest")


if __name__ == "__main__":
    # Run multiple chains if you want
    chains = ["BAREKET", "TIV_TAAM", "YELLOW"]

    for chain in chains:
        print(f"▶ Scraping {chain}...")
        run(chain)

    print("✅ Done scraping all chains.")