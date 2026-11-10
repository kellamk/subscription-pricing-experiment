"""Build a portable Power BI report and import model from the SQL summary."""

import json
from pathlib import Path


SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
REPORT_SCHEMA = f"{SCHEMA}/item/report"
TABLE = "Experiment"
REPORT = "Pricing Experiment.Report"
MODEL = "Pricing Experiment.SemanticModel"
PAGE = "a5d3a4a0078e40e29001"

MEASURES = {
    "Visitors": ("SUM(Experiment[visitors])", "#,0"),
    "Conversion rate": ("DIVIDE(SUM(Experiment[conversions]), [Visitors])", "0.00%"),
    "90-day retained per visitor": ("DIVIDE(SUM(Experiment[retained]), [Visitors])", "0.00%"),
    "Contribution per visitor": ("DIVIDE(SUM(Experiment[total_cents]), 100 * [Visitors])", "$0.00"),
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def projection(kind, name):
    return {
        "field": {kind: {"Expression": {"SourceRef": {"Entity": TABLE}}, "Property": name}},
        "queryRef": f"{TABLE}.{name}",
        "nativeQueryRef": name,
    }


def visual(name, position, title, visual_type, roles):
    x, y, width, height, order = position
    return {
        "$schema": f"{REPORT_SCHEMA}/definition/visualContainer/2.0.0/schema.json",
        "name": name,
        "position": dict(x=x, y=y, width=width, height=height, z=order, tabOrder=order),
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": {role: {"projections": fields} for role, fields in roles.items()}},
            "visualContainerObjects": {"title": [{"properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
            }}]},
        },
    }


def build_power_bi(root: Path, rows):
    write_json(root / "Pricing Experiment.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": REPORT}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(root / REPORT / "definition.pbir", {
        "$schema": f"{REPORT_SCHEMA}/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{MODEL}"}},
    })
    write_json(root / MODEL / "definition.pbism", {"version": "4.0", "settings": {}})

    keys = ["variant", "channel", "visitors", "conversions", "retained", "total_cents"]
    data = ",\n    ".join("{" + ", ".join(json.dumps(row[k]) for k in keys) + "}" for row in rows)
    types = ", ".join(f"{key} = {'text' if key in keys[:2] else 'Int64.Type'}" for key in keys)
    expression = f"#table(type table [{types}], {{\n    {data}\n}})"
    write_json(root / MODEL / "model.bim", {
        "name": "Pricing Experiment", "compatibilityLevel": 1600,
        "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3", "tables": [{
            "name": TABLE,
            "columns": [{"name": k, "sourceColumn": k, "summarizeBy": "none",
                         "dataType": "string" if k in keys[:2] else "int64",
                         "isHidden": k not in keys[:2]} for k in keys],
            "measures": [{"name": name, "expression": dax, "formatString": fmt}
                         for name, (dax, fmt) in MEASURES.items()],
            "partitions": [{"name": TABLE, "mode": "import",
                            "source": {"type": "m", "expression": expression.splitlines()}}],
        }]},
    })

    definition = root / REPORT / "definition"
    write_json(definition / "version.json", {
        "$schema": f"{REPORT_SCHEMA}/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0",
    })
    write_json(definition / "report.json", {
        "$schema": f"{REPORT_SCHEMA}/definition/report/3.1.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY25SU12",
            "reportVersionAtImport": {"visual": "2.5.0", "report": "3.1.0", "page": "2.3.0"},
            "type": "SharedResources"}},
    })
    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{REPORT_SCHEMA}/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [PAGE], "activePageName": PAGE,
    })
    page = definition / "pages" / PAGE
    write_json(page / "page.json", {
        "$schema": f"{REPORT_SCHEMA}/definition/page/2.0.0/schema.json",
        "name": PAGE, "displayName": "Pricing experiment | $29 vs $32",
        "displayOption": "FitToPage", "width": 1280, "height": 720,
    })
    for i, measure in enumerate(list(MEASURES)[1:]):
        name = f"{i + 1:020x}"
        write_json(page / "visuals" / name / "visual.json", visual(
            name, (24 + i * 416, 24, 400, 320, 1000 + i),
            measure, "barChart", {"Category": [projection("Column", "variant")],
                                  "Y": [projection("Measure", measure)]},
        ))
    name = f"{4:020x}"
    write_json(page / "visuals" / name / "visual.json", visual(
        name, (24, 368, 1232, 328, 1004), "Performance by channel and experiment arm", "tableEx",
        {"Values": [projection("Column", key) for key in ("channel", "variant")]
                   + [projection("Measure", key) for key in MEASURES]},
    ))
