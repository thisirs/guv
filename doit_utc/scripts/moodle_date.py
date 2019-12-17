from datetime import datetime, date

GROUP_ID = {
    'C1': 5377,
    'C2': 5378,
    'D1': 5379,
    'D10': 5388,
    'D11': 5389,
    'D12': 5390,
    'D2': 5380,
    'D3': 5381,
    'D4': 5382,
    'D5': 5383,
    'D6': 5384,
    'D7': 5385,
    'D8': 5386,
    'D9': 5387,
    'T1A': 5359,
    'T1Ai': 5391,
    'T1Aii': 5397,
    'T1B': 5371,
    'T1Bi': 5403,
    'T1Bii': 5409,
    'T2A': 5360,
    'T2Ai': 5392,
    'T2Aii': 5398,
    'T2B': 5372,
    'T2Bi': 5404,
    'T2Bii': 5410,
    'T3A': 5361,
    'T3Ai': 5393,
    'T3Aii': 5399,
    'T3B': 5373,
    'T3Bi': 5405,
    'T3Bii': 5411,
    'T4A': 5362,
    'T4Ai': 5394,
    'T4Aii': 5400,
    'T4B': 5374,
    'T4Bi': 5406,
    'T4Bii': 5412,
    'T5A': 5363,
    'T5Ai': 5395,
    'T5Aii': 5401,
    'T5B': 5375,
    'T5Bi': 5407,
    'T5Bii': 5413,
    'T6A': 5364,
    'T6Ai': 5396,
    'T6Aii': 5402,
    'T6B': 5376,
    'T6Bi': 5408,
    'T6Bii': 5414
}


class Cond:
    def __init__(self, sts=[]):
        self.visible = False
        self.sts = sts

    def to_PHP(self):
        return CondAnd(sts=[self]).to_PHP()

    def to_PHP_inner(self):
        raise NotImplementedError('Abstract method')

    def __and__(self, other):
        if isinstance(self, CondCompound):
            if isinstance(other, CondCompound):
                return CondAnd(sts=self.sts+other.sts)
            else:
                return CondAnd(sts=self.sts+[other])
        else:
            if isinstance(other, CondCompound):
                return CondAnd(sts=[self]+other.sts)
            else:
                return CondAnd(sts=[self]+[other])

    def __or__(self, other):
        if isinstance(self, CondCompound):
            if isinstance(other, CondCompound):
                return CondOr(sts=self.sts+other.sts)
            else:
                return CondOr(sts=self.sts+[other])
        else:
            if isinstance(other, CondCompound):
                return CondOr(sts=[self]+other.sts)
            else:
                return CondOr(sts=[self]+[other])


class CondDate(Cond):
    def __init__(self, sign=None, dt=None):
        super().__init__()
        self.sign = sign
        self.dt = dt

    def __ge__(self, other):
        if isinstance(other, (datetime, date)):
            return CondDate(sign='>=', dt=other)
        else:
            raise Exception()

    def __lt__(self, other):
        if isinstance(other, (datetime, date)):
            return CondDate(sign='<', dt=other)
        else:
            raise Exception()

    def to_PHP_inner(self):
        if type(self.dt) == date:
            dt = datetime.combine(self.dt, datetime.min.time())
        else:
            dt = self.dt

        ts = int(dt.timestamp())
        return {'type': 'date', 'd': self.sign, 't': ts}


class CondGroup(Cond):
    def __init__(self, grp=None):
        super().__init__()
        self.grp = grp

    def __eq__(self, other):
        if isinstance(other, str):
            return CondGroup(grp=other)
        else:
            raise Exception()

    def to_PHP_inner(self):
        id = GROUP_ID[self.grp]
        return {'type': 'group', 'id': id}


class CondCompound(Cond):
    def __init__(self, sts=[]):
        super().__init__(sts)
        self.negate = False

    def __not__(self):
        self.negate = not self.negate

    def to_PHP(self):
        e = self.to_PHP_inner()
        if (isinstance(self, CondAnd) and not self.negate) or \
           (isinstance(self, CondOr) and self.negate):
            key = 'showc'
            value = [e.visible for e in self.sts]
        else:
            key = 'show'
            value = self.visible

        e[key] = value

        return e


class CondOr(CondCompound):
    def to_PHP_inner(self):
        sts_PHP = [e.to_PHP_inner() for e in self.sts]
        op = '!|' if self.negate else '|'
        return {'op': op, 'c': sts_PHP}


class CondAnd(CondCompound):
    def to_PHP_inner(self):
        op = '!&' if self.negate else '&'
        sts_PHP = [e.to_PHP_inner() for e in self.sts]
        return {'op': op, 'c': sts_PHP}
