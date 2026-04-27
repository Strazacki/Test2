import hashlib
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd

SCIEZKI_PLIK = "/data/sciezki_516i511.txt"
WYNIK_PATH = "/data/ujednolicone_billingi.csv"
WYNIK_BEZ_MESSENGERA = "/data/ujednolicone_billingi_bez_messengera.csv"
LOG_PATH = "/data/ujednolicone_billingi.log"

SKIP_PATTERNS = [
    "emails_found.csv",
    "emails_found_short.csv",
    "Wyniki_Frazy_Slowa.csv",
]

ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "cp1250",
    "windows-1250",
    "iso-8859-2",
    "latin2",
    "latin1",
]

KIERUNEK_MAP = {
    "incoming": "Przychodzące",
    "outgoing": "Wychodzące",
    "missed": "Nieodebrane",
    "blocked": "Zablokowane",
    "rejected": "Odrzucone",
    "1": "Przychodzące",
    "2": "Wychodzące",
    "3": "Nieodebrane",
    "5": "Odrzucone",
}

_NON_DIGIT = re.compile(r"\D+")
_HAS_LETTER = re.compile(r"[A-Za-z]")


def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


log = logging.getLogger(__name__)


def fix_mojibake(value):
    if pd.isna(value):
        return ""
    s = str(value)
    replacements = {
        "Przychodz膮ce": "Przychodzące",
        "Wychodz膮ce": "Wychodzące",
        "Po艂膮czenie": "Połączenie",
    }
    for bad, good in replacements.items():
        s = s.replace(bad, good)

    if any(x in s for x in ["Å", "Ä", "Ã"]):
        try:
            return s.encode("latin1").decode("utf-8")
        except Exception:
            return s
    return s


def normalize_number(value) -> str:
    if pd.isna(value):
        return ""
    value = str(value).strip()
    if not value or value.upper() == "NULL" or value.lower() == "nan":
        return ""

    value = value.split("#")[0].strip()

    if _HAS_LETTER.search(value) and not value.startswith("+"):
        return value

    digits = _NON_DIGIT.sub("", value)

    if digits.startswith("0048") and len(digits) == 13:
        digits = digits[4:]
    elif digits.startswith("48") and len(digits) == 11:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = digits[1:]

    return digits if digits else value


def normalize_duration(value):
    if pd.isna(value):
        return ""

    v = str(value).strip().lower()
    if not v or v == "nan" or v == "null":
        return ""

    if "szt" in v:
        return ""

    if "mb" in v or "kb" in v or "gb" in v:
        return ""

    v = v.replace("min.", "").replace("min", "").strip()

    if re.fullmatch(r"\d{1,2}:\d{2}", v):
        m, s = v.split(":")
        return str(int(m) * 60 + int(s))

    if re.fullmatch(r"\d{1,3}:\d{2}:\d{2}", v):
        h, m, s = v.split(":")
        seconds = int(h) * 3600 + int(m) * 60 + int(s)
        if seconds > 24 * 3600:
            return ""
        return str(seconds)

    if re.fullmatch(r"\d+", v):
        return v

    return ""


def _sniff_sep(path: str, enc: str) -> str:
    try:
        with open(path, encoding=enc, errors="replace") as f:
            first = f.readline()
        if first.count(";") > first.count(","):
            return ";"
        for sep in [",", "\t", "|"]:
            if sep in first:
                return sep
    except Exception:
        pass
    return ","


def read_table(path: str) -> pd.DataFrame:
    ext = Path(path).suffix.lower()

    if ext in [".csv", ".txt"]:
        last_exc = None
        for enc in ENCODINGS:
            try:
                sep = _sniff_sep(path, enc)
                df = pd.read_csv(
                    path,
                    dtype=str,
                    sep=sep,
                    encoding=enc,
                    on_bad_lines="skip",
                    engine="python",
                ).fillna("")
                log.debug(f"  TXT/CSV odczytano enc={enc} sep={repr(sep)} shape={df.shape}")
                return df
            except Exception as e:
                last_exc = e
        raise ValueError(f"Nie udało się odczytać TXT/CSV: {last_exc}")

    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(path, dtype=str).fillna("")

    raise ValueError(f"Nieobsługiwany format: {ext}")


def parse_kv_line(line: str) -> dict:
    line = line.strip()
    line = re.sub(r"^Row:\s*\d+\s*", "", line)

    result = {}
    parts = re.split(r",\s+(?=[A-Za-z0-9_]+[=])", line)

    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        result[k.strip()] = v.strip()

    return result


def row_hash(row: dict) -> str:
    key = (
        f"{row.get('data_czas')}|{row.get('numer')}|{row.get('typ')}|"
        f"{row.get('kierunek')}|{str(row.get('tresc', ''))[:80]}"
    )
    return hashlib.md5(key.encode("utf-8", errors="ignore")).hexdigest()


def parse_call_logger(df, path):
    rows = []

    for _, row in df.iterrows():
        call_type = str(row.get("call_type", "")).replace("CallType.", "").lower()

        rows.append({
            "data_czas": pd.to_datetime(pd.to_numeric(row.get("timestamp", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
            "numer": normalize_number(row.get("number", "")),
            "nazwa_kontaktu": fix_mojibake(row.get("name", "")),
            "typ": "Połączenie",
            "kierunek": KIERUNEK_MAP.get(call_type, call_type),
            "czas_trwania": normalize_duration(row.get("duration", "")),
            "tresc": "",
            "plik_zrodlowy": path,
        })

    return rows


def parse_call_history_clean(df, path):
    rows = []

    for _, row in df.iterrows():
        call_type = str(row.get("type_label", row.get("type", ""))).lower().strip()

        rows.append({
            "data_czas": pd.to_datetime(pd.to_numeric(row.get("date", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
            "numer": normalize_number(row.get("normalized_number", "") or row.get("number", "")),
            "nazwa_kontaktu": fix_mojibake(row.get("name", "")),
            "typ": "Połączenie",
            "kierunek": KIERUNEK_MAP.get(call_type, call_type),
            "czas_trwania": normalize_duration(row.get("duration", "")),
            "tresc": "",
            "plik_zrodlowy": path,
        })

    return rows


def parse_txt_call_history(path):
    rows = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "date=" not in line or "number=" not in line:
                continue

            d = parse_kv_line(line)
            call_type = str(d.get("type", "")).lower()

            rows.append({
                "data_czas": pd.to_datetime(pd.to_numeric(d.get("date", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
                "numer": normalize_number(d.get("normalized_number", "") or d.get("number", "")),
                "nazwa_kontaktu": fix_mojibake(d.get("name", "")),
                "typ": "Połączenie",
                "kierunek": KIERUNEK_MAP.get(call_type, call_type),
                "czas_trwania": normalize_duration(d.get("duration", "")),
                "tresc": "",
                "plik_zrodlowy": path,
            })

    return rows


def parse_sms_export(df, path):
    rows = []

    for _, row in df.iterrows():
        sms_type = str(row.get("type", "")).strip()

        rows.append({
            "data_czas": pd.to_datetime(row.get("timestamp_warsaw", ""), utc=True, errors="coerce"),
            "numer": normalize_number(row.get("address", "")),
            "nazwa_kontaktu": fix_mojibake(row.get("contact_name", "")),
            "typ": "SMS",
            "kierunek": "Wychodzące" if sms_type == "2" else "Przychodzące",
            "czas_trwania": "",
            "tresc": fix_mojibake(row.get("body", "")),
            "plik_zrodlowy": path,
        })

    return rows


def parse_txt_sms_history(path):
    rows = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        buf = ""

        for raw in f:
            line = raw.rstrip("\n")

            if line.startswith("Row: ") and buf:
                rows.extend(parse_one_sms_kv(buf, path))
                buf = line
            else:
                buf += "\n" + line if buf else line

        if buf:
            rows.extend(parse_one_sms_kv(buf, path))

    return rows


def parse_one_sms_kv(text, path):
    d = parse_kv_line(text.replace("\n", "\\n"))
    if "date" not in d or "address" not in d:
        return []

    sms_type = str(d.get("type", "")).strip()

    return [{
        "data_czas": pd.to_datetime(pd.to_numeric(d.get("date", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
        "numer": normalize_number(d.get("address", "")),
        "nazwa_kontaktu": "",
        "typ": "SMS",
        "kierunek": "Wychodzące" if sms_type == "2" else "Przychodzące",
        "czas_trwania": "",
        "tresc": fix_mojibake(d.get("body", "")),
        "plik_zrodlowy": path,
    }]


def parse_messages(df, path):
    rows = []

    for _, row in df.iterrows():
        direction = str(row.get("direction", "")).upper().strip()
        if direction == "IN":
            kierunek = "Przychodzące"
        elif direction == "OUT":
            kierunek = "Wychodzące"
        else:
            kierunek = "Nieznany"

        rows.append({
            "data_czas": pd.to_datetime(pd.to_numeric(row.get("timestamp_ms", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
            "numer": normalize_number(row.get("address", "")),
            "nazwa_kontaktu": fix_mojibake(row.get("contact_name", "")),
            "typ": row.get("kind", "SMS") or "SMS",
            "kierunek": kierunek,
            "czas_trwania": "",
            "tresc": fix_mojibake(row.get("body", "")),
            "plik_zrodlowy": path,
        })

    return rows


def parse_messenger(df, path):
    rows = []
    own_names = {"Sebastian", "Seba"}

    for _, row in df.iterrows():
        sender = str(row.get("sender", "")).strip()

        rows.append({
            "data_czas": pd.to_datetime(row.get("datetime", ""), errors="coerce", utc=True),
            "numer": "",
            "nazwa_kontaktu": fix_mojibake(row.get("thread", "")),
            "typ": "Messenger",
            "kierunek": "Wychodzące" if sender in own_names else "Przychodzące",
            "czas_trwania": "",
            "tresc": fix_mojibake(row.get("text", "")),
            "plik_zrodlowy": path,
        })

    return rows


def parse_preview(df, path):
    rows = []

    for _, row in df.iterrows():
        raw = str(row.get("data", row.get(df.columns[0], ""))).strip()

        if not raw or "CallType." not in raw:
            continue

        parts = raw.split(",")
        if len(parts) < 8 or not str(parts[7]).isdigit():
            continue

        try:
            call_type = parts[4].replace("CallType.", "").lower()
            ts = pd.to_datetime(pd.to_numeric(parts[7], errors="coerce"), unit="ms", utc=True, errors="coerce")

            if pd.isna(ts) or ts.year < 2015:
                continue

            rows.append({
                "data_czas": ts,
                "numer": normalize_number(parts[2]),
                "nazwa_kontaktu": fix_mojibake(parts[0]),
                "typ": "Połączenie",
                "kierunek": KIERUNEK_MAP.get(call_type, call_type),
                "czas_trwania": normalize_duration(parts[1]),
                "tresc": "",
                "plik_zrodlowy": path,
            })
        except Exception:
            continue

    return rows


def parse_logger_xlsx(df, path):
    rows = []

    for _, row in df.iterrows():
        call_type = str(row.get("call type", "")).lower().strip()

        call_type_map = {
            "przychodzące": "Przychodzące",
            "wychodzące": "Wychodzące",
            "nieodebrane": "Nieodebrane",
            "zablokowane": "Zablokowane",
            "odrzucone": "Odrzucone",
        }

        rows.append({
            "data_czas": pd.to_datetime(pd.to_numeric(row.get("timestamp ms", ""), errors="coerce"), unit="ms", utc=True, errors="coerce"),
            "numer": normalize_number(row.get("number raw", "") or row.get("cached matched number", "")),
            "nazwa_kontaktu": fix_mojibake(row.get("name", "")),
            "typ": "Połączenie",
            "kierunek": call_type_map.get(call_type, fix_mojibake(call_type)),
            "czas_trwania": normalize_duration(row.get("duration s", "")),
            "tresc": "",
            "plik_zrodlowy": path,
        })

    return rows


def parse_billdata(df, path):
    rows = []

    for _, row in df.iterrows():
        raw_time = row.get("Czas trwania", "")
        typ = "SMS" if "szt" in str(raw_time).lower() or re.fullmatch(r"\d+", str(raw_time).strip()) else "Połączenie"

        rodzaj = str(row.get("Rodzaj połącz.", "")).lower()
        if "sms" in rodzaj:
            typ = "SMS"
        elif "mms" in rodzaj:
            typ = "MMS"
        elif "rozm" in rodzaj or "poł" in rodzaj:
            typ = "Połączenie"

        rows.append({
            "data_czas": pd.to_datetime(row.get("Data/Godz", ""), errors="coerce", utc=True),
            "numer": normalize_number(row.get("Wybrany numer", "")),
            "nazwa_kontaktu": "",
            "typ": typ,
            "kierunek": "Wychodzące",
            "czas_trwania": normalize_duration(raw_time),
            "tresc": "",
            "plik_zrodlowy": path,
        })

    return rows


def parse_xls_operator(df, path):
    rows = []

    header_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row.values]
        if "Kierunek" in vals and "Numer telefonu" in vals:
            header_row = i
            break

    if header_row is not None:
        sub = df.iloc[header_row:].copy()
        sub.columns = [str(v).strip() for v in sub.iloc[0].values]
        sub = sub.iloc[1:].reset_index(drop=True)
    else:
        sub = df.copy()

    for _, row in sub.iterrows():
        data = str(row.get("Data", "")).strip()
        godz = str(row.get("Godzina", "")).strip()

        if not data or data.lower() == "nan":
            continue

        ts = pd.to_datetime(f"{data} {godz}", errors="coerce", utc=True)

        numer = row.get("Numer telefonu", "")
        if str(numer).lower() in ["internet", "nan", ""]:
            continue

        rows.append({
            "data_czas": ts,
            "numer": normalize_number(numer),
            "nazwa_kontaktu": fix_mojibake(row.get("Nazwa", "")),
            "typ": fix_mojibake(row.get("Rodzaj aktywności", "Połączenie")),
            "kierunek": fix_mojibake(row.get("Kierunek", "")),
            "czas_trwania": normalize_duration(row.get("czas rozm.", row.get("min./kB/szt.", ""))),
            "tresc": "",
            "plik_zrodlowy": path,
        })

    return rows


def detect_and_parse(df, path):
    cols = set(df.columns)
    name = Path(path).name.lower()
    ext = Path(path).suffix.lower()

    if ext == ".txt" and "call_history" in name:
        log.info("  Format: txt_call_history")
        return parse_txt_call_history(path)

    if ext == ".txt" and "sms_history" in name:
        log.info("  Format: txt_sms_history")
        return parse_txt_sms_history(path)

    if {"call_type", "duration", "timestamp", "number"}.issubset(cols):
        log.info("  Format: call_logger")
        return parse_call_logger(df, path)

    if {"date", "duration", "type_label"}.issubset(cols) and ({"number"}.issubset(cols) or {"normalized_number"}.issubset(cols)):
        log.info("  Format: call_history_clean")
        return parse_call_history_clean(df, path)

    if {"timestamp_warsaw", "body", "address"}.issubset(cols):
        log.info("  Format: sms_export")
        return parse_sms_export(df, path)

    if {"timestamp_ms", "direction"}.issubset(cols):
        log.info("  Format: messages")
        return parse_messages(df, path)

    if {"thread", "datetime", "sender", "text"}.issubset(cols):
        log.info("  Format: messenger")
        return parse_messenger(df, path)

    if {"data godz", "call type", "number raw", "duration s", "timestamp ms"}.issubset(cols):
        log.info("  Format: logger_xlsx")
        return parse_logger_xlsx(df, path)

    if "preview" in name or (len(cols) >= 4 and "data" in cols and "numer" in cols):
        log.info("  Format: preview")
        return parse_preview(df, path)

    if {"Data/Godz", "Wybrany numer", "Czas trwania"}.issubset(cols):
        log.info("  Format: billdata")
        return parse_billdata(df, path)

    if {"Lp.", "Data", "Godzina", "Numer telefonu", "Kierunek"}.issubset(cols):
        log.info("  Format: xls_operator_direct")
        return parse_xls_operator(df, path)

    if ext in [".xls", ".xlsx"] and any(str(c).startswith("Unnamed") for c in cols):
        log.info("  Format: xls_operator_scan")
        return parse_xls_operator(df, path)

    return None


def main():
    setup_logging()
    log.info("=== START ujednolicania billingów v3 ===")

    with open(SCIEZKI_PLIK, "r", encoding="utf-8") as f:
        paths = [line.strip() for line in f if line.strip()]

    paths = sorted(set(paths))
    log.info(f"Plików do przetworzenia: {len(paths)}")

    all_rows = []
    seen_hashes = set()
    stats = {}

    for path in paths:
        if any(x in path for x in SKIP_PATTERNS):
            log.info(f"Pominięto skip_pattern: {path}")
            continue

        if not os.path.exists(path):
            log.warning(f"Brak pliku: {path}")
            continue

        log.info(f"Przetwarzam: {path}")
        stats[path] = {"records": 0, "duplicates": 0, "error": None}

        try:
            if Path(path).suffix.lower() == ".txt":
                df = pd.DataFrame()
            else:
                df = read_table(path)

                if len(df.columns) == 1 and "," in str(df.columns[0]):
                    first_col = df.columns[0]
                    split_cols = [x.strip() for x in first_col.split(",")]
                    df = df[first_col].str.split(",", expand=True)
                    df.columns = split_cols[:len(df.columns)]

            result = detect_and_parse(df, path)

            if result is None:
                cols = list(df.columns)[:12] if not df.empty else []
                log.warning(f"  Nieznany format — pomijam. Kolumny: {cols}")
                stats[path]["error"] = "nieznany format"
                continue

            added = 0
            dupes = 0

            for row in result:
                h = row_hash(row)
                if h in seen_hashes:
                    dupes += 1
                    continue

                seen_hashes.add(h)
                all_rows.append(row)
                added += 1

            stats[path]["records"] = added
            stats[path]["duplicates"] = dupes
            log.info(f"  Dodano: {added}, duplikatów: {dupes}")

        except Exception as e:
            log.error(f"  Błąd: {e}")
            stats[path]["error"] = str(e)

    if not all_rows:
        log.warning("Brak danych do ujednolicenia.")
        return

    final_df = pd.DataFrame(all_rows)

    final_df["data_czas"] = pd.to_datetime(final_df["data_czas"], errors="coerce", utc=True)
    final_df = final_df.dropna(subset=["data_czas"])
    final_df = final_df[final_df["data_czas"].dt.year >= 2015]
    final_df = final_df.sort_values("data_czas")

    final_df["data_czas"] = (
        final_df["data_czas"]
        .dt.tz_convert("Europe/Warsaw")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    for col in ["typ", "kierunek", "nazwa_kontaktu", "tresc"]:
        if col in final_df.columns:
            final_df[col] = final_df[col].apply(fix_mojibake)

    final_df.to_csv(WYNIK_PATH, index=False, encoding="utf-8-sig")

    bez_msg = final_df[final_df["typ"] != "Messenger"]
    bez_msg.to_csv(WYNIK_BEZ_MESSENGERA, index=False, encoding="utf-8-sig")

    log.info("\n" + "=" * 70)
    log.info(f"WYNIK: {WYNIK_PATH}")
    log.info(f"WYNIK bez Messengera: {WYNIK_BEZ_MESSENGERA}")


if __name__ == "__main__":
    main()
