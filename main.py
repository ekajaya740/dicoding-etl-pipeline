from pprint import pprint

from utils.extract import extract
from utils.transform import transform
from utils.load import load

def run(
    urls: list[str],
    csv_dir: str,
    gsheet_creds: str,
    gsheet_id: str,
    pg_host: str,
    pg_dbname: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, int | str]:
    raw = extract(urls)
    cleaned = list(transform(raw))

    results: dict[str, int | str] = {}

    results["csv"] = load(iter(cleaned), "csv", output_path=csv_dir)

    try:
        results["gsheet"] = load(
            iter(cleaned), "gsheet",
            credentials_file=gsheet_creds,
            spreadsheet_id=gsheet_id,
            sheet_name="Sheet1",
        )
    except Exception as e:
        results["gsheet"] = f"SKIPPED: {e}"

    try:
        results["postgresql"] = load(
            iter(cleaned), "postgresql",
            host=pg_host,
            dbname=pg_dbname,
            user=pg_user,
            password=pg_password,
            table="products",
        )
    except Exception as e:
        results["postgresql"] = f"SKIPPED: {e}"

    return results

if __name__ == "__main__":
    base_url = "https://fashion-studio.dicoding.dev"
    urls = []
    for i in range(1,51):
        if i == 1:
            urls.append(base_url)
        else:
            urls.append(f"{base_url}/page{i}")

    result = run(
        urls=urls,
        csv_dir=".",
        gsheet_creds="credentials.json",
        gsheet_id="1Pk4HCrc-bnir2FlgNQY_CPE-EOZfMvFT9r_Jwx_9SX8",
        pg_host="0.0.0.0",
        pg_dbname="etl",
        pg_user="postgres",
        pg_password="postgres",
    )
    pprint(result)
