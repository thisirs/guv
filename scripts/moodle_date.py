from datetime import datetime, date

GROUP_ID = {
     "C1": 4133,
     "C2": 4132,
     "D1": 4140,
     "D10": 4134,
     "D11": 4141,
     "D12": 4142,
     "D2": 4138,
     "D3": 4135,
     "D4": 4145,
     "D5": 4143,
     "D6": 4137,
     "D7": 4139,
     "D8": 4136,
     "D9": 4144,
     "enseignants": 2378,
     "T1A": 4306,
     "T1Ai": 4319,
     "T1Aii": 4329,
     "T1B": 4310,
     "T1Bi": 4323,
     "T1Bii": 4331,
     "T2A": 4301,
     "T2Ai": 4313,
     "T2Aii": 4316,
     "T2B": 4305,
     "T2Bi": 4318,
     "T2Bii": 4326,
     "T3A": 4304,
     "T3Ai": 4317,
     "T3Aii": 4333,
     "T3B": 4308,
     "T3Bi": 4321,
     "T3Bii": 4324,
     "T4A": 4299,
     "T4Ai": 4311,
     "T4Aii": 4327,
     "T4B": 4307,
     "T4Bi": 4320,
     "T4Bii": 4328,
     "T5A": 4309,
     "T5Ai": 4322,
     "T5Aii": 4334,
     "T5B": 4300,
     "T5Bi": 4312,
     "T5Bii": 4330,
     "T6A": 4302,
     "T6Ai": 4314,
     "T6Aii": 4325,
     "T6B": 4303,
     "T6Bi": 4315,
     "T6Bii": 4332
}


class Cond:
    def __init__(self, sts=[]):
        self.visible = False
        self.sts = sts

    def to_PHP(self):
        return CondAnd(sts=[self]).to_PHP()

    def to_PHP_inner():
        raise NotImplementedError('Abstract method')

    def __and__(self, other):
        if type(self) == CondAnd and type(other) == CondAnd:
            return CondAnd(sts=self.sts+other.sts)
        elif type(self) == CondAnd:
            return CondAnd(sts=self.sts+[other])
        elif type(other) == CondAnd:
            return CondAnd(sts=[self]+other.sts)
        else:
            return CondAnd(sts=[self, other])

    def __or__(self, other):
        if type(self) == CondOr or type(other) == CondOr:
            return CondOr(sts=self.sts+other.sts)
        elif type(self) == CondOr:
            return CondOr(sts=self.sts+[other.sts])
        elif type(other) == CondOr:
            return CondOr(sts=[self.sts]+other.sts)
        else:
            return CondOr(sts=[self.sts, other.sts])


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
