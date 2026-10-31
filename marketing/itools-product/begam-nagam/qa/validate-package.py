#!/usr/bin/env python3
"""Validate the handoff's actual contract, copy, image assets and safe file set."""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from jsonschema import Draft7Validator
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
REQUIRED = {"product-content.json", "product-copy.fa.md", "capabilities-inventory.md",
            "evidence.md", "screenshots-manifest.json", "handoff.md", "logo.svg"}
QA_FILES = {"browser-checks.json", "capture-records.json", "runtime-evidence.json",
            "source-integrity.json", "cleanup.json", "validation.json", "product-landing.schema.json",
            "run-demo.py", "check-browser.cjs", "build-package.py", "validate-package.py", "build-zip.py",
            "desktop-hero.webp", "qa-freeform-unavailable.png"}

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def main():
    for name in REQUIRED:
        check((ROOT / name).is_file(), f"Missing {name}")
    data = read("product-content.json")
    schema = read("qa/product-landing.schema.json")
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema).validate(data)
    check(data["sourceProductId"] is None, "Product ID must remain unknown")
    check(data["title"] == "بگم نگم" and data["titleEn"] == "BEGAM NAGAM", "Brand mismatch")
    check(len(data["summary"]) <= 160, "Summary exceeds target")
    check(data["modules"] == [], "Do not invent modules")
    check(6 <= len(data["features"]) <= 8, "Feature count")
    check(6 <= len(data["gallery"]) <= 8, "Gallery count")
    check(2 <= len(data["signature"]) <= 3, "Signature count")
    check(all(3 <= len(item["bullets"]) <= 5 for item in data["signature"]), "Signature bullet count")
    check(3 <= len(data["workflow"]) <= 5 and 6 <= len(data["faq"]) <= 8, "Workflow/FAQ count")
    check(3 <= len(data["tags"]) <= 5, "Tag count")
    ids = [item["id"] for item in data["gallery"]]
    check(len(ids) == len(set(ids)) and all(re.fullmatch(r"[a-z0-9-]+", i) for i in ids), "Gallery IDs")
    check(data["cta"]["href"] == "/#requestSupport", "CTA destination")
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
    values = list(strings(data))
    check(all(text.strip() for text in values), "Empty copy")
    check(not any(re.search(r"TODO|TBD|lorem ipsum|عنوان نهایی و مستند محصول", text, re.I) for text in values), "Placeholder copy")
    spec = importlib.util.spec_from_file_location("handoff_builder", ROOT / "qa/build-package.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    check((ROOT / "product-copy.fa.md").read_text(encoding="utf-8") == builder.render_copy(data), "Readable copy differs from JSON")
    manifest = read("screenshots-manifest.json")
    check(len({item["filename"] for item in manifest}) == len(manifest), "Duplicate screenshot")
    approved = [item for item in manifest if item["status"] == "approved"]
    check(len(approved) == 12, "Expected 12 approved screenshots")
    check(sum(item["width"] == 780 for item in approved) == 6, "Mobile count")
    check(sum(item["width"] == 1600 for item in approved) == 6, "Desktop count")
    required_keys = {"filename", "section", "caption", "alt", "width", "height", "bytes", "captureDate", "sourceVersion", "scenario"}
    for item in manifest:
        check(required_keys <= item.keys(), "Manifest fields")
        check(all(str(item[key]).strip() for key in required_keys), "Empty manifest field")
        path = ROOT / item["path"]
        check(path.is_file() and path.name == item["filename"], "Missing image")
        with Image.open(path) as im:
            im.load()
            check(im.size == (item["width"], item["height"]), "Image dimensions changed")
            if item["status"] == "approved":
                check(im.format == "WEBP", "Approved image must be WebP")
        check(path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], "Image integrity mismatch")
        check(datetime.fromisoformat(item["captureDate"]).utcoffset() is not None, "Missing capture timezone")
        check(item["sourceVersion"].startswith("0.16.1 (4c1ffce"), "Capture version mismatch")
        if item["status"] == "approved":
            check(path.parent == ROOT / "images", "Approved path")
            check(item["bytes"] < 350 * 1024, "Image size budget")
            check((item["width"], item["height"]) in [(780, 1688), (1600, 1000)], "Approved aspect")
        else:
            check(path.parent == ROOT / "qa", "Unapproved image escaped QA")
    references = [text for text in values if text.startswith("/images/")]
    names = {item["filename"] for item in approved}
    for reference in references:
        check(reference.startswith("/images/products/begam-nagam/"), "Image URL prefix")
        check(Path(reference).name in names, "Reference lacks approved image")
    for key in ("heroImage", "cardImage"):
        item = next(item for item in approved if item["filename"] == Path(data[key]).name)
        check((item["width"], item["height"]) == (1600, 1000), "Hero/card ratio")
    check(data["heroImage"] != data["cardImage"], "Card requires independent image")
    check({p.name for p in (ROOT / "images").iterdir()} == names, "Extra/missing public image")
    source = read("qa/source-integrity.json")
    check(not source["mismatches"] and source["exportedSourceFilesCompared"] == 527, "Source integrity")
    logo = next(item for item in source["sourceFiles"] if item["path"] == "frontend/public/icon.svg")
    check(sha(ROOT / "logo.svg") == logo["sha256"], "Logo modified")
    original_schema = next(item for item in source["companyReadOnlyFiles"] if item["path"].endswith("product-landing.schema.json"))
    check(sha(ROOT / "qa/product-landing.schema.json") == original_schema["sha256"], "Schema snapshot modified")
    browser = read("qa/browser-checks.json")
    check(browser["status"] == "passed" and len(browser["checks"]) == 12 and all(item["pass"] for item in browser["checks"]), "Browser QA")
    check(not browser["pageErrors"] and not browser["externalRequests"], "Unexpected browser requests/errors")
    runtime = read("qa/runtime-evidence.json")
    check(not any(runtime["credentialsPresent"].values()), "Credentials unexpectedly present")
    check(runtime["settings"]["PROVIDER_NETWORK_MODE"] == "disabled" and runtime["aiUsageRows"] == runtime["providerReservations"] == 0, "Unsafe demo evidence")
    cleanup = read("qa/cleanup.json")
    check(cleanup["runtimeRemoved"] and cleanup["temporaryServersStopped"], "Capture runtime not cleaned up")
    allowed = REQUIRED | {"images/" + name for name in names} | {"qa/" + name for name in QA_FILES}
    for path in ROOT.rglob("*"):
        check(not path.is_symlink(), "Symlink not allowed in handoff")
        if path.is_file():
            check(path.relative_to(ROOT).as_posix() in allowed, f"Unexpected file: {path.relative_to(ROOT)}")
    result = {
        "status": "passed", "checkedAt": datetime.now(ZoneInfo("Asia/Tehran")).isoformat(),
        "schema": "copied actual iTools draft-07 contract", "summaryCharacters": len(data["summary"]),
        "copyMatchesJsonExactly": True, "features": len(data["features"]), "gallery": len(data["gallery"]),
        "signature": len(data["signature"]), "workflow": len(data["workflow"]), "faq": len(data["faq"]),
        "approvedScreenshots": len(approved), "rejectedScreenshots": 1, "qaOnlyScreenshots": 1,
        "referencedImageOccurrences": len(references), "maxApprovedImageBytes": max(i["bytes"] for i in approved),
        "logoMatchesSource": True, "browserChecksPassed": 12, "allowedFileSetOnly": True,
        "captureSourceVersion": "0.16.1", "localContentPackageVersion": "0.16.2",
        "limitations": ["No current production verification", "No physical-device/PWA acceptance", "No paid AI, real SMS or payment in this review"],
    }
    (ROOT / "qa/validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
