# =========================================
# management command
# path: yourapp/management/commands/train_reel_recommender.py
# (yourapp/management/ மற்றும் yourapp/management/commands/ folders-ல
#  __init__.py empty file வேணும்)
#
# Run பண்ண: python manage.py train_reel_recommender
# =========================================

import torch
import torch.nn as nn
import numpy as np
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import User
from api.models import Reel, ReelLike, ReelComment, ReelView, ReelRecommendation
# ⚠️ 'yourapp' ஐ உங்க actual app name-ஆ மாத்தவும் (models.py இருக்கிற app)


EMBED_DIM   = 32
EPOCHS      = 15
LR          = 0.01
TOP_N       = 30          # ஒரு user-க்கு எவ்வளவு reels recommend பண்ணணும்
MIN_INTERACTIONS = 1       # cold-start users skip


# =========================================
# SIMPLE MATRIX FACTORIZATION MODEL (PyTorch)
# =========================================
class MFModel(nn.Module):
    def __init__(self, num_users, num_items, embed_dim=EMBED_DIM):
        super().__init__()
        self.user_emb = nn.Embedding(num_users, embed_dim)
        self.item_emb = nn.Embedding(num_items, embed_dim)
        nn.init.normal_(self.user_emb.weight, std=0.01)
        nn.init.normal_(self.item_emb.weight, std=0.01)

    def forward(self, u, i):
        return (self.user_emb(u) * self.item_emb(i)).sum(dim=1)


class Command(BaseCommand):
    help = "Train PyTorch BPR matrix-factorization model on reel interactions and store top-N recommendations"

    def handle(self, *args, **options):

        # ---------------------------------
        # STEP 1 — Build weighted interactions
        # like=3, comment=2, watch_ratio>0.5=1.5, view=1
        # ---------------------------------
        interactions = {}   # (user_id, reel_id) -> weight

        for uid, rid in ReelLike.objects.values_list('user_id', 'reel_id'):
            interactions[(uid, rid)] = interactions.get((uid, rid), 0) + 3

        for uid, rid in ReelComment.objects.values_list('user_id', 'reel_id'):
            interactions[(uid, rid)] = interactions.get((uid, rid), 0) + 2

        for uid, rid, ratio in ReelView.objects.values_list('user_id', 'reel_id', 'watch_ratio'):
            w = 1.5 if ratio and ratio > 0.5 else 1.0
            interactions[(uid, rid)] = interactions.get((uid, rid), 0) + w

        if not interactions:
            self.stdout.write(self.style.WARNING("No interactions found. Skipping training."))
            return

        user_ids = sorted({u for u, r in interactions})
        reel_ids = sorted({r for u, r in interactions})

        if len(user_ids) < 2 or len(reel_ids) < 2:
            self.stdout.write(self.style.WARNING("Not enough users/reels for training yet."))
            return

        user_idx = {u: i for i, u in enumerate(user_ids)}
        reel_idx = {r: i for i, r in enumerate(reel_ids)}
        idx_to_reel = {i: r for r, i in reel_idx.items()}

        # user -> set of reel indices they interacted with (positive samples)
        user_positive = {}
        for (u, r) in interactions:
            user_positive.setdefault(user_idx[u], set()).add(reel_idx[r])

        num_users = len(user_ids)
        num_items = len(reel_ids)

        # ---------------------------------
        # STEP 2 — BPR pairwise training pairs
        # (user, positive_item, negative_item)
        # ---------------------------------
        train_triplets = []
        all_item_indices = set(range(num_items))

        for u_idx, pos_set in user_positive.items():
            neg_candidates = list(all_item_indices - pos_set)
            if not neg_candidates:
                continue
            for pos_item in pos_set:
                neg_item = random.choice(neg_candidates)
                train_triplets.append((u_idx, pos_item, neg_item))

        if not train_triplets:
            self.stdout.write(self.style.WARNING("No valid training triplets."))
            return

        # ---------------------------------
        # STEP 3 — Train PyTorch model
        # ---------------------------------
        model = MFModel(num_users, num_items)
        optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)

        triplets_tensor = torch.tensor(train_triplets, dtype=torch.long)

        for epoch in range(EPOCHS):
            optimizer.zero_grad()
            u = triplets_tensor[:, 0]
            pos = triplets_tensor[:, 1]
            neg = triplets_tensor[:, 2]

            pos_scores = model(u, pos)
            neg_scores = model(u, neg)

            # BPR loss — pos score > neg score ஆகணும்
            loss = -torch.log(torch.sigmoid(pos_scores - neg_scores) + 1e-8).mean()
            loss.backward()
            optimizer.step()

            self.stdout.write(f"Epoch {epoch+1}/{EPOCHS} — loss: {loss.item():.4f}")

        # ---------------------------------
        # STEP 4 — Score all (user, item) pairs, pick top-N per user
        # (already-interacted reels-ஐ skip பண்ணி புது reels மட்டும் recommend)
        # ---------------------------------
        model.eval()
        with torch.no_grad():
            all_user_emb = model.user_emb.weight   # (num_users, dim)
            all_item_emb = model.item_emb.weight   # (num_items, dim)
            scores_matrix = all_user_emb @ all_item_emb.T   # (num_users, num_items)

        new_recs = []
        for u_idx, u_id in enumerate(user_ids):
            seen = user_positive.get(u_idx, set())
            scores = scores_matrix[u_idx].numpy()

            # already seen reels-ஐ score -inf ஆக்கி exclude பண்றோம்
            for seen_idx in seen:
                scores[seen_idx] = -np.inf

            top_indices = np.argsort(-scores)[:TOP_N]

            for rank, item_idx in enumerate(top_indices, start=1):
                if scores[item_idx] == -np.inf:
                    continue
                new_recs.append(ReelRecommendation(
                    user_id=u_id,
                    reel_id=idx_to_reel[item_idx],
                    score=float(scores[item_idx]),
                    rank=rank,
                ))

        # ---------------------------------
        # STEP 5 — DB-ல replace பண்றோம் (old recs delete → new insert)
        # ---------------------------------
        with transaction.atomic():
            ReelRecommendation.objects.filter(user_id__in=user_ids).delete()
            ReelRecommendation.objects.bulk_create(new_recs, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {len(new_recs)} recommendations stored for {len(user_ids)} users."
        ))