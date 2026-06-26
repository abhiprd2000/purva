from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .schema import Record, content_hash, JsonlWriter
from .clean import clean_sentence, split_sentences, strip_pii, normalize, has_devanagari, strip_markup
from .collect.reddit import RedditCollector


def process_devanagari(raw: str) -> list[str]:
    norm = normalize(strip_pii(strip_markup(raw)))
    out = []
    for s in split_sentences(norm):
        c = clean_sentence(s)
        if c:
            out.append(c)
    return out


def latin_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if "a" <= ch.lower() <= "z")
    return latin / len(letters)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    src = cfg["source"]

    collector = RedditCollector(
        source_name=src["source_name"],
        subreddit=src["subreddit"],
        user_agent=cfg["user_agent"],
        request_delay=src.get("request_delay", 2.0),
        max_posts=src.get("max_posts", 1000),
    )

    romanised_path = Path(src.get("romanised_output", "data/reddit_romanised_raw.jsonl"))
    romanised_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"collecting r/{src['subreddit']} (devanagari -> corpus, romanised -> side file)\n")
    start = time.time()
    kept = 0
    romanised = 0
    docs = 0

    with JsonlWriter(cfg["output"]) as writer, \
         romanised_path.open("a", encoding="utf-8") as rfh:
        for doc in collector.iter_documents():
            docs += 1
            text = doc.text
            if has_devanagari(text):
                for sent in process_devanagari(text):
                    rec = Record(
                        id=content_hash(sent),
                        raw_text=sent,
                        cleaned_text=sent,
                        source_url=doc.url,
                        source_name=doc.meta["source"],
                        scrape_timestamp=datetime.now(timezone.utc).isoformat(),
                        category=doc.meta.get("kind"),
                    )
                    if writer.add(rec):
                        kept += 1
            else:
                norm = normalize(strip_pii(strip_markup(text)))
                if len(norm) >= 15 and latin_ratio(norm) > 0.5:
                    rfh.write(json.dumps(
                        {"text": norm, "source_url": doc.url,
                         "kind": doc.meta.get("kind")},
                        ensure_ascii=False) + "\n")
                    romanised += 1
            if docs % 100 == 0:
                print(f"  {docs} items, {kept} devanagari sentences, {romanised} romanised banked")

        total = writer.written
        dupes = writer.skipped_dupes

    elapsed = time.time() - start
    print(f"\n--- reddit scrape summary ---")
    print(f"items processed  : {docs}")
    print(f"devanagari kept   : {total}")
    print(f"dupes skipped     : {dupes}")
    print(f"romanised banked  : {romanised} (side file, not in corpus)")
    print(f"elapsed           : {elapsed:.0f}s")
    print(f"corpus output     : {cfg['output']}")
    print(f"romanised output  : {romanised_path}")


if __name__ == "__main__":
    main()