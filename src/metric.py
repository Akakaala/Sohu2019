from ignite.metrics.metric import Metric
import re
import torch
from sklearn.metrics import f1_score
from pytorch_pretrained_bert.tokenization import BertTokenizer
from utils import covert_myids_to_mytokens, load_data, data_dump
import os
import numpy as np
from collections import defaultdict, Counter

# ID2TOK = load_data("../datasets/ID2TOK_lite.pkl")
# ID2TOK = load_data("../datasets/ID2TOK_lite.pkl")
# ID2TOK = load_data("../datasets/ID2TOK_full.pkl")
# ID2TOK = load_data("../datasets/ID2TOK_one_last_lite.pkl")
ID2TOK = load_data("../datasets/ID2TOK_one_last_full.pkl")


# ID2TOK = load_data("../datasets/ID2TOK_one_last_full.pkl")

# bert_token_model = "/home/lzk/llouice/.pytorch_pretrained_bert/8a0c070123c1f794c42a29c6904beb7c1b8715741e235bee04aca2c7636fc83f.9b42061518a39ca00b8b52059fd2bede8daa613f8a8671500e518a8c29de8c00"

class FScore(Metric):
    """
    Calculates the top-k categorical accuracy.

    - `update` must receive output of the form `(y_pred, y)`.
    """

    def __init__(self, output_transform=lambda x: x):
        self.EMOS_MAP = {"0":"OTHER","1": "POS", "2": "NEG", "3": "NORM"}
        self.ents = defaultdict(list)
        self.ents_pred = defaultdict(list)
        self.f1s_ent = []
        self.f1s_emo = []
        self.ones_pred = 0
        self.ones = 0
        # put the super in end!
        super(FScore, self).__init__(output_transform)

    def reset(self):
        self.ents.clear()
        self.ents_pred.clear()
        self.f1s_emo.clear()
        self.f1s_ent.clear()
        self.ones_pred = 0
        self.ones = 0

    def update(self, output):
        y_pred_ent, y_ent, y_pred_emo, y_emo, myinput_ids = output
        tokens = covert_myids_to_mytokens(ID2TOK, myinput_ids.tolist())
        y_pred_ent = torch.argmax(torch.softmax(y_pred_ent, dim=-1), dim=-1)  # [L, 1]
        y_pred_emo = torch.argmax(torch.softmax(y_pred_emo, dim=-1), dim=-1)  # [L, 1]
        self._count(y_pred_ent, y_ent, y_pred_emo, y_emo, tokens)

    def _count(self, y_pred_ent, y_ent, y_pred_emo, y_emo, tokens):
        '''become str of nums the use re to match'''
        y_pred_ent = "".join([str(i.item()) for i in y_pred_ent])
        y_ent = "".join([str(i.item()) for i in y_ent])
        y_pred_emo = "".join([str(i.item()) for i in y_pred_emo])
        y_emo = "".join([str(i.item()) for i in y_emo])
        pattern = re.compile("1[2]")  # 贪婪匹配
        self._find_ents(y_pred_ent, y_pred_emo, pattern, tokens, self.ents_pred, "pred")
        self._find_ents(y_ent,y_emo, pattern, tokens, self.ents)
        ENTS_PRED = {ent for ent in self.ents_pred}
        ENTS = {ent for ent in self.ents}

        # 实体的分数
        f1_ent = self.cal_f1(ENTS_PRED, ENTS)
        self.f1s_ent.append(f1_ent)

        # 情感的分数
        EMOS_S_PRED = set()
        EMOS_S = set()
        for ent, emos in self.ents_pred.items():
            c = Counter(emos).most_common(1)
            EMOS_S_PRED.add("{}_{}".format(ent, self.EMOS_MAP[c[0][0]]))
        for ent, emos in self.ents.items():
            c = Counter(emos).most_common(1)
            EMOS_S.add("{}_{}".format(ent, self.EMOS_MAP[c[0][0]]))
        f1_emo = self.cal_f1(EMOS_S_PRED, EMOS_S)
        self.f1s_emo.append(f1_emo)
        self.ents_pred.clear()
        self.ents.clear()

    def compute(self):
        f1_ent_all = np.average(self.f1s_ent) if len(self.f1s_ent) > 0 else 0
        f1_emo_all = np.average(self.f1s_emo) if len(self.f1s_emo) > 0 else 0
        print("单字数: {}/{}".format(self.ones_pred, self.ones))
        print(f"F1_ent: {f1_ent_all}\tF1_emo: {f1_emo_all}")
        return 0.5 * (f1_ent_all + f1_emo_all)

    def _find_ents(self, y_pred_ent,y_pred_emo, p, tokens, S, mode="lbl"):
        # TODO 使用与取result一致的逻辑
        for r in p.finditer(y_pred_ent):
            i, j = r.span()[0], r.span()[1]
            res = "".join(tokens[i:j])
            if len(res) == 1:
                if mode == "pred":
                    self.ones_pred += 1
                else:
                    self.ones += 1
                continue
            emos = y_pred_emo[i:j]
            emo = Counter(emos).most_common(1)[0][0]
            S[res].append(emo)

    def cal_f1(self, s1, s2):
        nb_correct = len(s1 & s2)
        nb_pred = len(s1)
        nb_true = len(s2)
        p = nb_correct / nb_pred if nb_pred > 0 else 0
        r = nb_correct / nb_true if nb_true > 0 else 0
        f1 = (2 * p * r) / (p + r) if p + r > 0 else 0
        return f1
