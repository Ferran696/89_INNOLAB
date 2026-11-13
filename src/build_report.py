"""Build an offline HTML and JSON summary from local processing outputs."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from .reporting import analyze_telemetry, n2_per_counted_unit, read_csv_rows, summarize_clip
except ImportError:
    from reporting import analyze_telemetry, n2_per_counted_unit, read_csv_rows, summarize_clip


def _number(value: Any, suffix: str = "") -> str:
    if value is None:
        return "No disponible"
    return f"{value}{suffix}"


def _origin_label(origin: str) -> str:
    return {
        "real": "Captura real autoritzada",
        "simulated": "SIMULACIÓ",
        "unknown": "Origen no identificat",
    }.get(origin, "Origen no identificat")


def _timeline(intervals: list[dict[str, str]], duration_s: float) -> str:
    items: list[str] = []
    colors = {
        "visually_empty": "#e4a11b",
        "detections_present": "#27885a",
        "unevaluable": "#777b85",
    }
    for row in intervals:
        start = float(row.get("time_start_s") or 0)
        duration = float(row.get("duration_s") or 0)
        quality = row.get("quality", "unevaluable")
        width = duration / duration_s * 100 if duration_s > 0 else 0
        label = f"{start:.2f}–{start + duration:.2f} s: {quality}"
        items.append(
            "<span class=\"segment\" style=\"width:{:.4f}%;background:{}\" "
            "title=\"{}\" aria-label=\"{}\"></span>".format(
                max(width, 0),
                colors.get(quality, colors["unevaluable"]),
                html.escape(label, quote=True),
                html.escape(label, quote=True),
            )
        )
    return "\n".join(items)


def render_html(
    summary: dict[str, Any],
    intervals: list[dict[str, str]],
    output_path: Path,
    video_path: Path | None,
) -> str:
    origin = html.escape(_origin_label(summary["clip_origin"]))
    recommendation = html.escape(summary["observation"])
    counts = summary["counts_by_recipe"] or {"Cap trajectòria comptada": 0}
    recipe_rows = "".join(
        f"<tr><td>{html.escape(str(recipe))}</td><td>{int(count)}</td></tr>"
        for recipe, count in counts.items()
    )

    video_block = "<p>No s'ha adjuntat cap vídeo anotat.</p>"
    if video_path is not None:
        video_uri = Path(os.path.relpath(video_path.resolve(), output_path.parent.resolve())).as_posix()
        video_block = (
            f'<video controls preload="metadata" src="{html.escape(video_uri, quote=True)}">'
            "El navegador no pot reproduir aquest fitxer local.</video>"
        )

    telemetry = summary["telemetry"]
    if telemetry.get("status") == "available":
        telemetry_origin = _origin_label(telemetry["origin"])
        telemetry_total = f"{telemetry['n2_kg_total']:.3f} kg ({html.escape(telemetry_origin)})"
    else:
        telemetry_total = html.escape(telemetry.get("reason", "No disponible"))

    n2_ratio = summary["n2_per_counted_unit"]
    if n2_ratio["status"] == "available":
        n2_value = f"{n2_ratio['value']:.6f} kg/peça ({html.escape(_origin_label(n2_ratio['origin']))})"
    elif n2_ratio["status"] == "not_applicable_zero_units":
        n2_value = "No aplicable: denominador zero"
    else:
        n2_value = "No disponible: manca telemetria sincronitzada o el clip no és avaluable"

    return f"""<!doctype html>
<html lang="ca">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FreezeProof — resum local</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #202a35; background: #f3f5f7; }}
    body {{ max-width: 1050px; margin: 0 auto; padding: 28px 18px; }}
    header, section {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 10px #142b3a12; }}
    h1, h2 {{ margin-top: 0; }}
    .badge {{ display: inline-block; padding: 5px 10px; border-radius: 999px; background: #e8edf2; font-weight: 700; }}
    .warning {{ border-left: 5px solid #d88a00; padding: 10px 14px; background: #fff6df; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
    .metric {{ background: #f5f7f9; padding: 14px; border-radius: 9px; }}
    .metric strong {{ display: block; font-size: 1.35rem; margin-top: 6px; }}
    video {{ width: 100%; max-height: 65vh; background: #111; border-radius: 8px; }}
    .timeline {{ display: flex; width: 100%; height: 24px; overflow: hidden; border-radius: 6px; background: #777b85; }}
    .segment {{ min-width: 1px; border-right: 1px solid #fff9; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 10px; }}
    .dot {{ display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 5px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #e2e6ea; }}
    footer {{ color: #4c5965; font-size: .9rem; padding: 6px 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>FreezeProof — resum de demostració</h1>
    <p>Clip: <strong>{html.escape(str(summary['clip_id']))}</strong></p>
    <p><span class="badge">{origin}</span> <span class="badge">Estimacions de visió per computador</span></p>
    <p class="warning"><strong>No és un comptador homologat ni una liquidació.</strong>
    El recompte d'entrada no certifica producte acabat; RGB no mesura pes, temperatura interior,
    congelació correcta ni seguretat alimentària.</p>
  </header>
  <section>
    <h2>Vídeo anotat</h2>
    {video_block}
  </section>
  <section>
    <h2>Indicadors visuals</h2>
    <div class="metrics">
      <div class="metric">Recompte direccional<strong>{summary['counted_units']} peces</strong></div>
      <div class="metric">Ritme en temps avaluable<strong>{_number(summary['pieces_per_minute'], ' peces/min')}</strong></div>
      <div class="metric">Intervals visualment sense deteccions<strong>{summary['visually_empty_seconds']:.2f} s</strong></div>
      <div class="metric">Càrrega visual aproximada<strong>{_number(summary['approx_occupancy_score'])}</strong></div>
      <div class="metric">Durada avaluable<strong>{summary['evaluable_seconds']:.2f} / {summary['video_duration_s']:.2f} s</strong></div>
    </div>
    <p>Un interval “visualment sense deteccions” vol dir que el model no ha detectat productes
    en imatges avaluables; no prova que la cinta estigui físicament buida. La càrrega és un
    índex aproximat de deteccions respecte del valor de referència configurat, no una superfície
    real ni una capacitat tèrmica.</p>
  </section>
  <section>
    <h2>Traça temporal (qualitat d'imatge i deteccions)</h2>
    <div class="timeline" role="img" aria-label="Intervals del vídeo">{_timeline(intervals, summary['video_duration_s'])}</div>
    <div class="legend">
      <span><i class="dot" style="background:#27885a"></i>Deteccions presents</span>
      <span><i class="dot" style="background:#e4a11b"></i>Visualment sense deteccions</span>
      <span><i class="dot" style="background:#777b85"></i>No avaluable</span>
    </div>
  </section>
  <section>
    <h2>Unitats comptades per recepta</h2>
    <table><thead><tr><th>Referència (selecció manual)</th><th>Peces</th></tr></thead>
    <tbody>{recipe_rows}</tbody></table>
  </section>
  <section>
    <h2>Telemetria opcional</h2>
    <p><strong>N₂ total en la finestra sincronitzada:</strong> {telemetry_total}</p>
    <p><strong>N₂ per peça:</strong> {html.escape(n2_value)}</p>
    <p>Una dada simulada no es presenta com a mesura real. Sense cobertura temporal completa,
    origen i túnel identificats, o amb intervals no avaluables, N₂/unitat no s'informa.</p>
  </section>
  <section>
    <h2>Observació per contrastar</h2>
    <p>{recommendation}</p>
  </section>
  <footer>
    Origen del clip: {origin}. El vídeo i aquest informe es generen localment; no incorporis
    fitxers reals o dades de client a un repositori o servei extern sense autorització explícita.
    El resultat només és una demostració no facturable.
  </footer>
</body>
</html>
"""


def build_report(
    events_path: Path,
    occupancy_path: Path,
    output_path: Path,
    video_path: Path | None = None,
    telemetry_path: Path | None = None,
    telemetry_offset_s: float = 0.0,
    empty_run_alert_seconds: float = 2.0,
) -> None:
    if not events_path.is_file() or not occupancy_path.is_file():
        raise FileNotFoundError("Both events.csv and occupancy.csv must exist")
    if video_path is not None and not video_path.is_file():
        raise FileNotFoundError(f"Annotated video not found: {video_path}")

    events = read_csv_rows(events_path)
    intervals = read_csv_rows(occupancy_path)
    summary = summarize_clip(events, intervals, empty_run_alert_seconds)
    telemetry = analyze_telemetry(
        telemetry_path,
        summary["video_duration_s"],
        telemetry_offset_s,
    )
    summary["telemetry"] = telemetry
    summary["n2_per_counted_unit"] = n2_per_counted_unit(telemetry, summary)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_html(summary, intervals, output_path, video_path), encoding="utf-8"
    )
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Offline HTML report: {output_path}")
    print(f"Summary JSON: {json_path}")


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=Path("outputs/events.csv"))
    parser.add_argument("--occupancy", type=Path, default=Path("outputs/occupancy.csv"))
    parser.add_argument("--video", type=Path, help="optional annotated video to link locally")
    parser.add_argument("--telemetry", type=Path, help="optional synchronized telemetry CSV")
    parser.add_argument("--telemetry-offset-s", type=float, default=0.0)
    parser.add_argument("--empty-run-alert-seconds", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=Path("outputs/report.html"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        build_report(
            args.events,
            args.occupancy,
            args.output,
            args.video,
            args.telemetry,
            args.telemetry_offset_s,
            args.empty_run_alert_seconds,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())