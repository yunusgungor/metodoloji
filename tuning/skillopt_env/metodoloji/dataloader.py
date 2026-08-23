"""Metodoloji senaryo dataloader'ı."""
from __future__ import annotations

from skillopt.datasets.base import SplitDataLoader


class MetodolojiDataLoader(SplitDataLoader):
    """Senaryo split'lerini (train/val/test/items.json) yükler.

    Varsayılan ``load_split_items`` her split dizinindeki ``items.json``
    dosyasını okur; özel normalizasyon gerekmez.

    Her item: ``id``, ``task_type``, ``language``, ``user_request``,
    opsiyonel ``context`` ve ``expect{...}`` beklenti bloğu.
    """
