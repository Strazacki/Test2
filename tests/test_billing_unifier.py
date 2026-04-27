import pandas as pd

from billing_unifier import detect_and_parse, read_table


def test_single_column_header_split_padding():
    header = "Data/Godz,Numer,Wybrany numer,Czas trwania,Strefa,Szczyt,Kwota netto [zł]"
    df = pd.DataFrame(
        {
            header: [
                "2026-01-01 12:00:00,,+48123123123,39,PL,1,0.00,EXTRA_FIELD",
            ]
        }
    )

    first_col = df.columns[0]
    split_cols = [x.strip() for x in first_col.split(",")]
    df = df[first_col].str.split(",", expand=True)
    if len(split_cols) < len(df.columns):
        split_cols += [f"extra_{i}" for i in range(len(df.columns) - len(split_cols))]
    df.columns = split_cols[:len(df.columns)] if len(split_cols) > len(df.columns) else split_cols

    assert len(df.columns) == 8
    assert df.columns[-1] == "extra_0"


def test_cleaned_calls_datetime_variant():
    df = pd.DataFrame(
        [
            {
                "datetime": "2026-01-01 10:00:00+00:00",
                "number": "+48111222333",
                "name": "Test Contact",
                "call_type": "incoming",
                "duration": "84",
            }
        ]
    )

    rows = detect_and_parse(df, "cleaned_calls.csv")

    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["typ"] == "Połączenie"
    assert rows[0]["numer"] == "111222333"
    assert rows[0]["czas_trwania"] == "84"


def test_android_call_log_csv_call_history_clean():
    df = pd.DataFrame(
        [
            {
                "_id": "1",
                "date": "1700000000000",
                "duration": "114",
                "type": "2",
                "type_label": "outgoing",
                "number": "",
                "normalized_number": "+48999111222",
                "name": "Synthetic Name",
            }
        ]
    )

    rows = detect_and_parse(df, "android_call_log.csv")

    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["typ"] == "Połączenie"
    assert rows[0]["numer"] == "999111222"
    assert rows[0]["kierunek"] == "Wychodzące"


def test_messenger_rtc_detection():
    df = pd.DataFrame(
        [
            {
                "pk": "1",
                "thread_key": "thread-xyz",
                "call_type": "audio",
                "call_media_type": "voice",
                "call_state": "ended",
                "call_direction": "incoming",
                "thread_type": "one_to_one",
                "call_timestamp_ms": "1700000000000",
                "call_duration": "39",
            }
        ]
    )

    rows = detect_and_parse(df, "messenger_rtc.csv")

    assert rows is not None
    assert len(rows) == 1
    assert rows[0]["typ"] == "Messenger"
    assert rows[0]["kierunek"] == "Przychodzące"
    assert rows[0]["czas_trwania"] == "39"
    assert "audio" in rows[0]["tresc"]


def test_empty_csv_and_txt_do_not_crash(tmp_path):
    empty_csv = tmp_path / "empty.csv"
    empty_txt = tmp_path / "empty.txt"
    empty_csv.write_text("", encoding="utf-8")
    empty_txt.write_text("", encoding="utf-8")

    df_csv = read_table(str(empty_csv))
    df_txt = read_table(str(empty_txt))

    assert df_csv.empty
    assert df_txt.empty
