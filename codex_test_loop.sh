#!/usr/bin/env bash
set -u

LOG_PATH="/data/ujednolicone_billingi.log"
CSV_MAIN="/data/ujednolicone_billingi.csv"
CSV_NO_MSG="/data/ujednolicone_billingi_bez_messengera.csv"

START_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p /data >/dev/null 2>&1 || true
: > "$LOG_PATH"

echo "=== codex_test_loop start: ${START_TS} ==="

PY_COMPILE_OK=0
PYTEST_OK=0
SCRIPT_OK=0
CSV_OK=0
CRITICAL_LOG_OK=0

if python -m py_compile billing_unifier.py; then
  PY_COMPILE_OK=1
  echo "py_compile: OK"
else
  echo "py_compile: FAIL"
fi

if pytest -q; then
  PYTEST_OK=1
  echo "pytest: OK"
else
  echo "pytest: FAIL"
fi

if python billing_unifier.py; then
  SCRIPT_OK=1
  echo "billing_unifier.py: OK"
else
  echo "billing_unifier.py: FAIL"
fi

if [[ -f "$CSV_MAIN" && -f "$CSV_NO_MSG" ]]; then
  CSV_OK=1
  echo "wynikowe CSV: OK"
else
  echo "wynikowe CSV: FAIL"
fi

# Log jest czyszczony na starcie, więc analizujemy tylko aktualny przebieg.
if [[ -f "$LOG_PATH" ]]; then
  if rg -n "Traceback|Length mismatch|\bERROR\b" "$LOG_PATH" >/tmp/codex_critical_hits.txt; then
    # ignoruj wpisy znane jako warning/skipped
    if rg -n "Nieznany format — pomijam|skipped_|Uszkodzony plik Excel — pomijam" /tmp/codex_critical_hits.txt >/dev/null; then
      rg -n -v "Nieznany format — pomijam|skipped_|Uszkodzony plik Excel — pomijam" /tmp/codex_critical_hits.txt >/tmp/codex_critical_real.txt || true
    else
      cp /tmp/codex_critical_hits.txt /tmp/codex_critical_real.txt
    fi
  else
    : > /tmp/codex_critical_real.txt
  fi

  if [[ ! -s /tmp/codex_critical_real.txt ]]; then
    CRITICAL_LOG_OK=1
    echo "critical parser errors in log: none"
  else
    echo "critical parser errors found:"
    cat /tmp/codex_critical_real.txt
  fi
else
  echo "log file missing: $LOG_PATH"
fi

STATUS="FAIL"
if [[ $PY_COMPILE_OK -eq 1 && $PYTEST_OK -eq 1 && $SCRIPT_OK -eq 1 && $CSV_OK -eq 1 && $CRITICAL_LOG_OK -eq 1 ]]; then
  if rg -n "Nieznany format — pomijam|skipped_|Uszkodzony plik Excel — pomijam|\bWARNING\b" "$LOG_PATH" >/dev/null 2>&1; then
    STATUS="OK_WITH_WARNINGS"
  else
    STATUS="OK"
  fi
fi

echo "STATUS: ${STATUS}"

if [[ "$STATUS" == "FAIL" ]]; then
  exit 1
fi

exit 0
