"""
log_viewer.py — Visor de accesos de ProductoraClips
Uso:  python log_viewer.py [opciones]

Opciones:
  --ip IP           Filtrar por IP
  --action ACCION   Filtrar por acción (ej: subir_foto)
  --date FECHA      Filtrar por fecha UTC (ej: 2026-04-08)
  --status CODIGO   Filtrar por status HTTP (ej: 200, 400)
  --last N          Mostrar solo las últimas N entradas
  --export FILE     Exportar resultado a CSV
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

LOG_FILE = Path(__file__).parent / "logs" / "access.log"

COLS = ["ts", "ip", "method", "path", "status", "ms", "action"]


def load_entries(filters: dict) -> list[dict]:
    if not LOG_FILE.exists():
        print(f"[log_viewer] No existe {LOG_FILE}", file=sys.stderr)
        return []

    entries = []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue

            if filters.get("ip")     and e.get("ip")     != filters["ip"]:
                continue
            if filters.get("action") and e.get("action") != filters["action"]:
                continue
            if filters.get("date")   and not (e.get("ts") or "").startswith(filters["date"]):
                continue
            if filters.get("status") and str(e.get("status")) != str(filters["status"]):
                continue
            entries.append(e)

    if filters.get("last"):
        entries = entries[-filters["last"]:]
    return entries


def print_table(entries: list[dict]) -> None:
    widths = {c: len(c) for c in COLS}
    rows = [{c: str(e.get(c) or "") for c in COLS} for e in entries]
    for r in rows:
        for c in COLS:
            widths[c] = max(widths[c], len(r[c]))

    sep = "+-" + "-+-".join("-" * widths[c] for c in COLS) + "-+"
    header = "| " + " | ".join(c.ljust(widths[c]) for c in COLS) + " |"
    print(sep)
    print(header)
    print(sep)
    for r in rows:
        print("| " + " | ".join(r[c].ljust(widths[c]) for c in COLS) + " |")
    print(sep)


def print_summary(entries: list[dict]) -> None:
    if not entries:
        print("(sin entradas)")
        return

    ips     = Counter(e.get("ip")     for e in entries)
    actions = Counter(e.get("action") for e in entries)
    errors  = [e for e in entries if (e.get("status") or 0) >= 400]

    print(f"\nTotal: {len(entries)} requests | IPs únicas: {len(ips)}")

    print("\n-- Acciones más frecuentes --")
    for action, n in actions.most_common(10):
        print(f"  {n:>5}x  {action}")

    print("\n-- Actividad por IP --")
    for ip, n in ips.most_common(15):
        print(f"  {n:>5}x  {ip}")

    if errors:
        print(f"\n-- Errores ({len(errors)}) --")
        for e in errors[-10:]:
            print(f"  [{e.get('status')}] {e.get('method')} {e.get('path')}  {e.get('ts','')[:19]}  {e.get('ip')}")


def export_csv(entries: list[dict], path: str) -> None:
    all_keys = list({k for e in entries for k in e})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)
    print(f"Exportado a {path}  ({len(entries)} filas)")


def main():
    parser = argparse.ArgumentParser(description="Visor de logs de ProductoraClips")
    parser.add_argument("--ip",     help="Filtrar por IP")
    parser.add_argument("--action", help="Filtrar por acción")
    parser.add_argument("--date",   help="Filtrar por fecha UTC (YYYY-MM-DD)")
    parser.add_argument("--status", help="Filtrar por status HTTP")
    parser.add_argument("--last",   type=int, help="Últimas N entradas")
    parser.add_argument("--export", metavar="FILE", help="Exportar a CSV")
    args = parser.parse_args()

    filters = {k: v for k, v in vars(args).items() if v is not None and k != "export"}
    entries = load_entries(filters)

    if not entries:
        print("No hay entradas que coincidan con los filtros.")
        return

    print_table(entries)
    print_summary(entries)

    if args.export:
        export_csv(entries, args.export)


if __name__ == "__main__":
    main()
