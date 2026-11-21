"""Verify the paired study's frozen inputs and print the decision counts."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECISIONS = ("immediate", "committee", "recommend", "conditional", "decline")


def read_json(name):
    return json.loads((ROOT / name).read_text())


def fingerprint(text):
    return sha256(text.encode()).hexdigest()


def monthly_basket(quantity, packages):
    # Resolve ties by fewer purchases, then by package size.
    ledger = [(0, 0, ())]
    for needed in range(1, quantity + 1):
        candidates = []
        for size, price in packages:
            cost, orders, sizes = ledger[max(0, needed - size)]
            candidates.append((price + cost, orders + 1, (size,) + sizes))
        ledger.append(min(candidates))
    cost, _, sizes = ledger[-1]
    quantities = "، ".join(f"{v} × {k}" for k, v in sorted(Counter(sizes).items()))
    return f"{cost:,} تومان، تعداد بسته‌ها به صورت تعداد × اندازه: {quantities}"


def main():
    profiles = read_json("profiles.json")
    observations = read_json("public-observations.json")
    packages = sorted((p["message_count"], p["price_toman"])
                      for p in observations["bootstrap"]["observed_fields"]["message_packages"] if p["active"])
    shared = (ROOT / "evidence-1.fa.txt").read_text()
    delta = (ROOT / "evidence-2-delta.fa.txt").read_text()
    instruction = (ROOT / "protocol.fa.txt").read_text().rstrip("\n")
    pairs = read_json("judgments.json")
    expected_ids = [f"P{i:03}" for i in range(1, 101)]
    assert [p["id"] for p in profiles] == [j["id"] for j in pairs] == expected_ids
    group_sizes = Counter(p["group"] for p in profiles)
    assert len(group_sizes) == 10 and set(group_sizes.values()) == {10}

    run_ids = set()
    totals = [Counter(), Counter()]
    transitions = Counter()
    for profile, pair in zip(profiles, pairs, strict=True):
        record = json.dumps(profile, ensure_ascii=False, sort_keys=True)
        basket = monthly_basket(profile["monthly_messages"], packages)
        for i, evidence in enumerate((shared, shared + "\n" + delta), start=1):
            run = pair[f"round_{i}"]
            answer = run["answer"]
            prompt = (instruction + "\n" + evidence + "\nپروندهٔ ثابت:\n" + record
                      + "\nسبد کافی برای ارسال همهٔ تعامل‌ها: " + basket)
            assert run["round"] == i and answer["id"] == profile["id"]
            assert fingerprint(evidence) == run["evidence_hash"]
            assert fingerprint(record) == run["profile_hash"]
            assert fingerprint(prompt) == run["prompt_hash"]
            assert answer["decision"] in DECISIONS
            assert answer["decision"] != "committee" or profile["authority"] == "کمیته"
            assert answer["decision"] != "immediate" or profile["authority"] in {"شخصی", "مستقل"}
            assert run["run_id"] not in run_ids
            run_ids.add(run["run_id"])
            totals[i - 1][answer["decision"]] += 1
        transitions[pair["round_1"]["answer"]["decision"], pair["round_2"]["answer"]["decision"]] += 1
    assert len(run_ids) == 200
    for i, counts in enumerate(totals, start=1):
        print(f"Round {i}", {d: counts[d] for d in DECISIONS})
    print("Changed", sum(v for (a, b), v in transitions.items() if a != b))


if __name__ == "__main__":
    main()
