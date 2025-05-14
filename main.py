"""
main.py: třetí projekt do Engeto Online Python Akademie

author: Jiri Mastny
email: mastnyj@seznam.cz
"""

import sys
import requests
from bs4 import BeautifulSoup
import csv

# Zkontroluje správnost argumentů při spuštění skriptu
# Očekává se URL a název výstupního CSV souboru
def validate_arguments():
    if len(sys.argv) != 3:
        print("Chyba: Musíte zadat URL a název výstupního souboru.", flush=True)
        sys.exit(1)
    url = sys.argv[1]
    output_file = sys.argv[2]
    if not url.startswith("https://www.volby.cz/pls/ps2017nss/ps32"):
        print("Chyba: Zadaný odkaz není platný pro volby 2017.", flush=True)
        sys.exit(1)
    return url, output_file

# Stáhne HTML a vytvoří soup objekt pro další analýzu
def get_soup(url, session):
    response = session.get(url)
    if response.status_code != 200:
        print(f"Chyba: Nepodařilo se stáhnout stránku {url}.", flush=True)
        sys.exit(1)
    return BeautifulSoup(response.text, "html.parser")

# Z hlavní stránky územního celku extrahuje seznam obcí a získá detailní data
def extract_data(soup, base_url, session):
    data = []
    all_party_names = []
    tables = soup.find_all("table")
    if not tables:
        print("Chyba: Nepodařilo se najít tabulky s daty.", flush=True)
        sys.exit(1)

    for table in tables:
        for row in table.find_all("tr")[2:]:
            columns = row.find_all("td")
            if len(columns) < 3:
                continue
            code = columns[0].text.strip()
            name = columns[1].text.strip()
            if code == "-" or not code.isdigit():
                continue
            link = columns[-1].find("a")
            if link:
                relative_url = link["href"]
                full_url = "https://www.volby.cz/pls/ps2017nss/" + relative_url
                registered, envelopes, valid, votes = scrape_detailed_data(full_url, session)
                for party in votes:
                    if party not in all_party_names and party != "-" and party != "":
                        all_party_names.append(party)
            else:
                registered, envelopes, valid, votes = 0, 0, 0, {}
            row_votes = [votes.get(party, 0) for party in all_party_names]
            data.append([code, name, registered, envelopes, valid, *row_votes])
    return data, all_party_names

# Najde konkrétní statistiku podle názvu (náhradní řešení)
def extract_stat_by_label(soup, label):
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) >= 2 and label in tds[0].text:
            return int(tds[1].text.strip().replace("\xa0", "").replace(" ", ""))
    return 0

# Najde <td> element podle částečného názvu atributu "headers"
def find_td_by_partial_header(soup, header_substring):
    return soup.find(lambda tag: tag.name == "td" and tag.has_attr("headers") and header_substring in tag["headers"])

# Bezpečný výběr hodnoty s fallbackem – zkusí najít podle atributu, jinak podle názvu
def extract_safe_stat(soup, header_key, label):
    td = find_td_by_partial_header(soup, header_key)
    if td and td.text.strip():
        return int(td.text.strip().replace("\xa0", "").replace(" ", ""))
    return extract_stat_by_label(soup, label)

# Načte detailní volební data z obce nebo všech okrsků obce
def scrape_detailed_data(url, session):
    soup = get_soup(url, session)

    # Obec má více okrsků – načíst data z každého zvlášť
    if "ps33" in url:
        okrsky_odkazy = [a for a in soup.find_all("a", href=True) if "xokrsek=" in a["href"]]
        total_registered = 0
        total_envelopes = 0
        total_valid = 0
        total_votes = {}
        for a in okrsky_odkazy:
            href = a.get("href", "")
            if href.startswith("http"):
                okrsek_url = href
            else:
                okrsek_url = "https://www.volby.cz/pls/ps2017nss/" + href
            reg, env, val, votes = scrape_detailed_data(okrsek_url, session)
            total_registered += reg
            total_envelopes += env
            total_valid += val
            for party, count in votes.items():
                total_votes[party] = total_votes.get(party, 0) + count
        return total_registered, total_envelopes, total_valid, total_votes

    # Obec má jeden okrsek – načíst přímo z jedné stránky
    registered = extract_safe_stat(soup, "sa2", "Voliči v seznamu")
    envelopes = extract_safe_stat(soup, "sa3", "Vydané obálky")
    valid = extract_safe_stat(soup, "sa6", "Platné hlasy")

    votes = {}
    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) >= 3:
            party_name = tds[1].text.strip()
            vote_count = tds[2].text.strip().replace("\xa0", "").replace(" ", "")
            if party_name and vote_count.isdigit():
                votes[party_name] = int(vote_count)

    return registered, envelopes, valid, votes

# Uloží data do výstupního CSV souboru
def save_to_csv(data, filename, party_names):
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        header = ["code", "location", "registered", "envelopes", "valid"] + party_names
        writer.writerow(header)
        for row in data:
            writer.writerow(row)
    print(f"Data byla uložena do souboru {filename}.", flush=True)

# Hlavní funkce skriptu
def main():
    url, output_file = validate_arguments()
    base_url = "https://www.volby.cz/pls/ps2017nss/"
    session = requests.Session()
    soup = get_soup(url, session)
    data, party_names = extract_data(soup, base_url, session)
    save_to_csv(data, output_file, party_names)

if __name__ == "__main__":
    main()
