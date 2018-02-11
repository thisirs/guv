from datetime import datetime, date


class Cond:
    def __init__(self, sts=[]):
        self.sts = sts

    def to_PHP():
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

    def __gt__(self, other):
        if isinstance(other, (datetime, date)):
            return CondDate(sign='>', dt=other)
        else:
            raise Exception()

    def __lt__(self, other):
        if isinstance(other, (datetime, date)):
            return CondDate(sign='<', dt=other)
        else:
            raise Exception()

    def to_PHP(self):
        sign_PHP = {'>': '&gt;=', '<': '&lt;='}[self.sign]
        if type(self.dt) == date:
            dt = datetime.combine(self.dt, datetime.min.time())
        else:
            dt = self.dt

        ts = int(dt.timestamp())
        return f'{{"type": "date", "d": {sign_PHP}, "t": {ts}}}'


class CondGroup(Cond):
    def __init__(self, grp=None):
        super().__init__()
        self.grp = grp

    def __eq__(self, other):
        if isinstance(other, str):
            return CondGroup(grp=other)
        else:
            raise Exception()

    def to_PHP(self):
        return f'{{"type": "group", "id": "id"}}'


class CondOr(Cond):
    def to_PHP(self):
        sts_PHP = ', '.join(e.to_PHP() for e in self.sts)
        return f'{{"op": "|", "c": [{sts_PHP}]}}'


class CondAnd(Cond):
    def to_PHP(self):
        sts_PHP = ', '.join(e.to_PHP() for e in self.sts)
        return f'{{"op": "&", "c": [{sts_PHP}]}}'
