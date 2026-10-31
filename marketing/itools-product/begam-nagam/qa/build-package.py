#!/usr/bin/env python3
"""Assemble evidence already captured; does not access a browser or any provider."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def render_copy(data):
    labels = {
        "sourceProductId": "شناسهٔ محصول در سایت شرکت", "title": "نام فارسی", "titleEn": "نام انگلیسی",
        "category": "دسته‌بندی", "headline": "عنوان اصلی", "summary": "معرفی کوتاه", "accent": "رنگ",
        "visual": "نوع تصویر جایگزین", "tags": "برچسب‌ها", "heroImage": "تصویر اصلی", "cardImage": "تصویر کارت",
        "eyebrow": "روتیتر", "introTitle": "عنوان معرفی", "intro": "معرفی مسئله و رویکرد", "releaseStatus": "وضعیت محصول",
        "features": "قابلیت‌ها", "gallery": "گالری", "signature": "بخش‌های متمایز", "modules": "ماژول‌ها",
        "integrations": "اتصال‌ها", "workflow": "مراحل استفاده", "faq": "پرسش‌های متداول", "cta": "اقدام نهایی",
        "icon": "نماد", "description": "توضیح", "status": "وضعیت", "id": "شناسهٔ نما", "image": "تصویر",
        "alt": "متن جایگزین تصویر", "layout": "چیدمان", "bullets": "نکته‌ها", "name": "نام سرویس",
        "question": "پرسش", "answer": "پاسخ", "label": "متن دکمه", "href": "مقصد دکمه",
    }
    lines = ["# متن نهایی معرفی بگم نگم", "", "ترتیب و تمام مقادیر از product-content.json تولید شده‌اند؛ عنوان‌های توضیحی جزو متن قالب نیستند.", ""]
    def visit(value, key=None, level=2):
        if key is not None:
            lines.extend(["#" * min(level, 6) + " " + labels.get(key, key) + f" — {key}", ""])
        if isinstance(value, dict):
            for child, item in value.items():
                visit(item, child, level + 1)
        elif isinstance(value, list):
            if not value:
                lines.extend(["[]", ""])
            for index, item in enumerate(value, 1):
                if isinstance(item, dict):
                    lines.extend(["#" * min(level + 1, 6) + f" مورد {index}", ""])
                    visit(item, level=level + 1)
                else:
                    lines.extend(["- " + str(item), ""])
        else:
            lines.extend(["null" if value is None else str(value), ""])
    for key, value in data.items():
        visit(value, key)
    return "\n".join(lines)

def main():
    from PIL import Image
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((ROOT / "product-content.json").read_text())
    (ROOT / "product-copy.fa.md").write_text(render_copy(data), encoding="utf-8")
    shutil.copyfile(args.schema, ROOT / "qa/product-landing.schema.json")
    shutil.copyfile(args.repo / "frontend/public/icon.svg", ROOT / "logo.svg")
    records = json.loads((ROOT / "qa/capture-records.json").read_text())
    gallery = {Path(item["image"]).name: item for item in data["gallery"]}
    extras = {
        "desktop-reminder-compose.webp": ("فرم واقعی دسکتاپ برای نمونهٔ یادآوری استفاده از تلفن؛ تم تیره و دادهٔ آزمایشی.", "فرم دسکتاپ بگم نگم با دستهٔ گفت‌وگو و رابطه و نمونهٔ استفاده از تلفن در کادر پیام."),
        "desktop-appreciation-compose.webp": ("نمای مستقل کارت محصول: شروع قدردانی از نمونهٔ بررسی‌شده در دموی واقعی.", "فرم دسکتاپ با دستهٔ حال خوب و نمونهٔ تشکر و قدردانی انتخاب‌شده."),
        "desktop-support.webp": ("ثبت یک پرسش مصنوعی در پشتیبانی خصوصی؛ پاسخی از کارکنان شبیه‌سازی نشده است.", "پنجرهٔ پشتیبانی روی رابط دسکتاپ با پرسش مصنوعی دربارهٔ تفاوت ثبت درخواست و تحویل پیام."),
        "desktop-demo-credit.webp": ("خرید آزمایشی بستهٔ سه‌پیامی، پس از پاداش دعوت؛ هیچ وجهی جابه‌جا نشده است.", "صفحهٔ اعتبار با نتیجهٔ خرید آزمایشی، سه اعتبار آزمایشی و چهار هدیهٔ باقیمانده."),
        "desktop-hero.webp": ("رد برای انتشار: صفحهٔ آغاز دسکتاپ شامل جای‌نگهدار نشان‌های اعتماد است؛ گواهی یا درگاه فعال را اثبات نمی‌کند.", "صفحهٔ اصلی دسکتاپ با جای‌نگهدار لوگوی اینماد و درگاه بانکی؛ فقط برای بررسی داخلی."),
    }
    manifest = []
    for record in records:
        filename = record["filename"]
        approved = filename != "desktop-hero.webp"
        directory = "images" if approved else "qa"
        destination = ROOT / directory / filename
        if approved and not destination.exists():
            (ROOT / "qa" / filename).rename(destination)
        item = gallery.get(filename)
        caption, alt = (item["description"], item["alt"]) if item else extras[filename]
        with Image.open(destination) as im:
            width, height = im.size
        manifest.append({
            **record, "caption": caption, "alt": alt, "width": width, "height": height,
            "bytes": destination.stat().st_size,
            "captureDate": datetime.fromisoformat(record["captureDate"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Tehran")).isoformat(),
            "status": "approved" if approved else "rejected", "path": f"{directory}/{filename}",
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        })
    # This screenshot is supporting QA evidence, not a marketing gallery image.
    error_image = ROOT / "qa/qa-freeform-unavailable.png"
    with Image.open(error_image) as im:
        width, height = im.size
    manifest.append({
        "filename": error_image.name, "section": "qa", "caption": "خطای کنترل‌شده با متن خنثی: بازنویسی متن دلخواه در این دمو فعال نیست؛ انتخاب نمونه پیشنهاد می‌شود.",
        "alt": "فرم موبایل در عرض ۳۷۵ پیکسل با پیام خطای بازنویسی غیرفعال و متن خنثی قدردانی.",
        "width": width, "height": height, "bytes": error_image.stat().st_size,
        "captureDate": datetime.fromtimestamp(error_image.stat().st_mtime, ZoneInfo("Asia/Tehran")).isoformat(),
        "sourceVersion": records[0]["sourceVersion"], "scenario": "controlled-freeform-error",
        "status": "qa-only", "path": "qa/" + error_image.name,
        "sha256": hashlib.sha256(error_image.read_bytes()).hexdigest(),
        "captureDateBasis": "original screenshot file modification time",
    })
    dump(ROOT / "screenshots-manifest.json", manifest)

if __name__ == "__main__":
    main()
