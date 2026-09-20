#!/usr/bin/env python3
"""Build immutable, dependency-aware localization audit-cycle evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCALIZATION = ROOT / "Documentation" / "Localization"
SOURCE = LOCALIZATION / "Source" / "en" / "source.en.json"
INVENTORY = LOCALIZATION / "inventory.json"
PROJECT_REGRESSION_AUDIT = LOCALIZATION / "nl.audit.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical_json_sha(value: Any) -> str:
    return sha_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def ordered_ids(ids: set[str], order: dict[str, int]) -> list[str]:
    missing = sorted(ids - order.keys())
    if missing:
        raise SystemExit(f"Unknown localization IDs: {missing}")
    return sorted(ids, key=order.__getitem__)


def list_bytes(ids: list[str]) -> bytes:
    return ("" if not ids else "\n".join(ids) + "\n").encode("utf-8")


def write_list(path: Path, ids: list[str]) -> dict[str, Any]:
    data = list_bytes(ids)
    path.write_bytes(data)
    return {"file": path.name, "count": len(ids), "sha256": sha_bytes(data)}


def git_head_units(manual_path: Path) -> dict[str, str]:
    relative = manual_path.relative_to(ROOT).as_posix()
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
    )
    return json.loads(raw)["units"]


def resolve_changed_ids(
    spec: dict[str, Any], manual_path: Path, target: dict[str, str]
) -> set[str]:
    if "changedIdsFromAudit" in spec:
        audit = load_json(ROOT / spec["changedIdsFromAudit"])
        return set(audit["findings"]["changedUnitIds"])
    if spec.get("changedIdsFromGitHead"):
        baseline = git_head_units(manual_path)
        return {identifier for identifier, value in target.items() if baseline[identifier] != value}
    return set(spec.get("changedIds", []))


def main() -> int:
    args = parse_args()
    spec = load_json(args.spec)
    output = args.output
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty audit cycle: {output}")
    output.mkdir(parents=True, exist_ok=True)

    locale = spec["locale"]
    manual_path = LOCALIZATION / f"{locale}.manual.json"
    overlay_path = LOCALIZATION / f"{locale}.overlay.json"
    images_path = LOCALIZATION / f"{locale}.images.manual.json"
    source_doc = load_json(SOURCE)
    rows = source_doc["units"]
    source_by_id = {row["id"]: row for row in rows}
    order = {row["id"]: index for index, row in enumerate(rows)}
    target = load_json(manual_path)["units"]
    target.update(spec.get("targetOverrides", {}))

    changed = resolve_changed_ids(spec, manual_path, target)
    corrected = set(spec.get("correctedIds", []))

    context: set[str] = set()
    for identifier in changed:
        index = order[identifier]
        group = rows[index]["group"]
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(rows) and rows[neighbor]["group"] == group:
                context.add(rows[neighbor]["id"])
    context -= changed

    changed_source_texts = {source_by_id[identifier]["sourceText"] for identifier in changed}
    repetitions = {
        row["id"]
        for row in rows
        if row["sourceText"] in changed_source_texts and row["id"] not in changed
    }

    referent_terms = tuple(term.casefold() for term in spec.get("referentSearchTerms", []))
    glossary_referents = {
        row["id"]
        for row in rows
        if any(term in row["sourceText"].casefold() for term in referent_terms)
    }
    invalidated = set(spec.get("invalidatedIds", []))
    nontranslatable_dependencies = sorted(
        set(spec.get("nonTranslatableDynamicDependencies", []))
    )

    regression = load_json(PROJECT_REGRESSION_AUDIT)["dependencyClosure"]
    runtime_and_ui = set(regression["runtimeAndUiIds"])
    audit_catalog = load_json(PROJECT_REGRESSION_AUDIT)
    save_load_and_environment = set(
        audit_catalog["mandatoryRegression"]["saveLoadAndEnvironment"][
            "displayUnitIds"
        ]
    )
    mandatory_regression = (
        set(regression["genderRegressionIds"])
        | runtime_and_ui
        | save_load_and_environment
    )

    components = {
        "changed-ids.txt": changed,
        "context-ids.txt": context,
        "repetition-ids.txt": repetitions,
        "glossary-referent-ids.txt": glossary_referents,
        "invalidated-dependency-ids.txt": invalidated,
        "runtime-binding-ids.txt": runtime_and_ui,
        "mandatory-regression-ids.txt": mandatory_regression,
    }
    ordered_components = {
        filename: ordered_ids(ids, order) for filename, ids in components.items()
    }
    closure = ordered_ids(set().union(*components.values()), order)
    ordered_components["closure-ids.txt"] = closure

    previous_closure: set[str] = set()
    if spec.get("previousClosure"):
        previous_path = ROOT / spec["previousClosure"]
        previous_closure = set(previous_path.read_text(encoding="utf-8").splitlines())
    delta = corrected | (set(closure) - previous_closure) | invalidated
    removed = previous_closure - set(closure)
    if previous_closure:
        ordered_components["delta-review-ids.txt"] = ordered_ids(delta, order)
        ordered_components["removed-closure-ids.txt"] = ordered_ids(removed, order)

    component_evidence = {
        filename.removesuffix(".txt"): write_list(output / filename, ids)
        for filename, ids in ordered_components.items()
    }
    if nontranslatable_dependencies:
        filename = "non-translatable-dynamic-dependencies.txt"
        component_evidence[filename.removesuffix(".txt")] = write_list(
            output / filename, nontranslatable_dependencies
        )

    review_rows = []
    for identifier in closure:
        source_row = source_by_id[identifier]
        review_rows.append(
            {
                "id": identifier,
                "sourceText": source_row["sourceText"],
                "targetText": target[identifier],
                "group": source_row["group"],
                "kind": source_row["kind"],
                "speaker": source_row.get("speaker"),
                "context": source_row["context"],
            }
        )
    review_data = b"".join(
        (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        for row in review_rows
    )
    (output / "review-rows.jsonl").write_bytes(review_data)

    images = load_json(images_path)["images"]
    image_data = (
        json.dumps(images, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    )
    (output / "image-review-rows.json").write_bytes(image_data)

    glossary_source_path = Path(spec["glossarySource"])
    glossary_translations_path = Path(spec["glossaryTranslations"])
    glossary_source = load_json(glossary_source_path)
    glossary_layer = load_json(glossary_translations_path)[locale]
    frozen = spec.get("artifactHashes") or {
        "manual": sha_file(manual_path),
        "overlay": sha_file(overlay_path),
        "images": sha_file(images_path),
    }
    manifest = {
        "schemaVersion": 1,
        "locale": locale,
        "cycle": spec["cycle"],
        "status": spec["status"],
        "result": spec.get("result"),
        "reviewer": spec.get("reviewer"),
        "steamBuildId": "20535215",
        "gameVersion": "1.01",
        "sourceFingerprint": source_doc["sourceFingerprint"],
        "artifactHashes": frozen,
        "inputHashes": {
            "source": sha_file(SOURCE),
            "inventory": sha_file(INVENTORY),
            "glossarySourceNormalized": canonical_json_sha(glossary_source),
            "glossaryLocaleNormalized": canonical_json_sha(glossary_layer),
        },
        "newlineConvention": "UTF-8; ID lists use LF after every ID including the final ID; JSONL uses one compact JSON object plus LF per row.",
        "components": component_evidence,
        "reviewRows": {
            "file": "review-rows.jsonl",
            "count": len(review_rows),
            "sha256": sha_bytes(review_data),
        },
        "imageReviewRows": {
            "file": "image-review-rows.json",
            "count": len(images),
            "sha256": sha_bytes(image_data),
        },
        "correctedIds": ordered_ids(corrected, order),
        "findingCount": spec.get("findingCount"),
        "notes": spec.get("notes", []),
    }
    manifest_data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (output / "manifest.json").write_bytes(manifest_data)
    print(json.dumps({"output": str(output), "closureCount": len(closure), "reviewRowCount": len(review_rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
