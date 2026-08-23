"""Evaluator smoke testleri — fixture transcript'ler üzerinde uçtan uca skorlama."""
import json
import os
import sys

import pytest

TUNING_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(TUNING_ROOT, "skillopt_env"))

from metodoloji.evaluator import evaluate  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_item(item_id: str) -> dict:
    for split in ("train", "val", "test"):
        path = os.path.join(TUNING_ROOT, "data", "metodoloji_split", split, "items.json")
        for item in json.load(open(path, encoding="utf-8")):
            if item["id"] == item_id:
                return item
    raise AssertionError(f"item yok: {item_id}")


def _fixture(name: str) -> str:
    return open(os.path.join(FIXTURES, name), encoding="utf-8").read()


def test_good_mod_a_scores_full():
    scores = evaluate(_fixture("good_mod_a.md"), _load_item("TRA-A01"))
    assert scores["hard"] == 1, scores["problems"]
    assert scores["soft"] == pytest.approx(1.0), scores


def test_bad_mod_a_fails_on_honesty_and_fields():
    scores = evaluate(_fixture("bad_mod_a.md"), _load_item("TRA-A01"))
    assert scores["hard"] == 0
    assert scores["components"]["honesty"] == 0.0  # git commit -m + uydurma ölçüm
    assert scores["components"]["fields"] < 1.0
    assert scores["soft"] < 0.6


def test_good_honesty_refusal_passes():
    scores = evaluate(_fixture("good_honesty.md"), _load_item("TRA-H01"))
    assert scores["hard"] == 1, scores["problems"]
    assert scores["soft"] == pytest.approx(1.0)


def test_bad_honesty_breach_fails():
    scores = evaluate(_fixture("bad_honesty.md"), _load_item("TRA-H01"))
    assert scores["hard"] == 0
    assert scores["components"]["honesty"] == 0.0


def test_good_routing_passes():
    scores = evaluate(_fixture("good_routing.md"), _load_item("TRA-R01"))
    assert scores["hard"] == 1, scores["problems"]
    assert scores["components"]["routing"] == 1.0


def test_good_dev_chain_order_and_fields():
    scores = evaluate(_fixture("good_dev_chain.md"), _load_item("TRA-D01"))
    assert scores["hard"] == 1, scores["problems"]
    assert scores["soft"] == pytest.approx(1.0)


def test_wrong_chain_order_fails_hard():
    text = _fixture("good_dev_chain.md")
    # IR ve SP bloklarını yer değiştir (sıra ihlali)
    ir_start = text.index('<kayit tip="IR"')
    sp_start = text.index('<kayit tip="SP"')
    ir_end = text.index("</kayit>", ir_start) + len("</kayit>")
    sp_end = text.index("</kayit>", sp_start) + len("</kayit>")
    swapped = text[:ir_start] + text[sp_start:sp_end] + "\n" + text[ir_start:ir_end] + text[sp_end:]
    scores = evaluate(swapped, _load_item("TRA-D01"))
    assert scores["components"]["chain"] < 1.0
    assert scores["hard"] == 0
