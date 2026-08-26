"""Leave-one-farm-out validation of the fleet risk model.

The number quoted in the pitch has to be reproducible on demand, so it lives
in a script rather than in a slide. Training AUC is not evidence — the model
has seen that data. This holds an entire farm out, trains on the other three,
and scores the unseen one. That is exactly the claim being made: a new
customer inherits the fleet's learned weights and gets useful predictions on
day one, before contributing a single row of their own history.

    python3 -m cloud.validate
"""
from __future__ import annotations

import os
import random
import sys
from datetime import datetime, timezone

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "cloud"

from .fleet import RiskModel, build_dataset          # noqa: E402
from .seed import FARMS, farm_seed, simulate          # noqa: E402


def run(days: int = 30, verbose: bool = True):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hists = {}
    for f in FARMS:
        rng = random.Random(farm_seed(f["id"]))
        hists[f["id"]], _ = simulate(f, days, end, rng)

    if verbose:
        print("LEAVE-ONE-FARM-OUT — train on the fleet, score the unseen farm\n")
        print(f"{'held out':<15}{'train win':>10}{'pos':>6}"
              f"{'test win':>10}{'pos':>6}{'train AUC':>11}{'TEST AUC':>10}")

    rows, aucs = [], []
    for f in FARMS:
        Xtr, ytr = build_dataset([h for i, h in hists.items() if i != f["id"]])
        Xte, yte = build_dataset([hists[f["id"]]])
        if sum(yte) == 0 or sum(ytr) == 0:
            if verbose:
                print(f"{f['id']:<15}{len(Xtr):>10}{sum(ytr):>6}"
                      f"{len(Xte):>10}{sum(yte):>6}{'—':>11}{'no incidents':>18}")
            continue
        m = RiskModel.train(Xtr, ytr)
        a = m.auc(Xte, yte)
        aucs.append(a)
        rows.append({"farm": f["id"], "train_auc": m.meta["auc"],
                     "test_auc": round(a, 3), "test_positives": sum(yte)})
        if verbose:
            print(f"{f['id']:<15}{len(Xtr):>10}{sum(ytr):>6}"
                  f"{len(Xte):>10}{sum(yte):>6}{m.meta['auc']:>11}{a:>10.3f}")

    mean = sum(aucs) / len(aucs) if aucs else 0.0
    if verbose:
        print(f"\nmean held-out AUC: {mean:.3f}   "
              f"(0.5 = coin flip, 1.0 = perfect)")
        print("This is the number to quote. Training AUC is not evidence.")
    return {"rows": rows, "mean_auc": round(mean, 3), "folds": len(aucs)}


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
