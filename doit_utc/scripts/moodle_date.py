"""
DSL to express Moodle constraints
"""

from datetime import datetime, date


class Cond:
    def __init__(self, sts=[]):
        self.visible = False
        self.sts = sts

    def to_PHP(self, **info):
        return CondAnd(sts=[self]).to_PHP(**info)

    def to_PHP_inner(self, **info):
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

    def to_PHP_inner(self, **info):
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

    def group_id(self, **info):
        if self.grp not in info["group_id"]:
            raise Exception(f"Le groupe nommé {self.grp} n'a pas d'identifiant Moodle dans la variable GROUP_ID")
        return info["group_id"][self.grp]

    def to_PHP_inner(self, **info):
        return {'type': 'group', 'id': self.group_id(**info)}


class CondProfil(Cond):
    def __init__(self, field, value=None, rel=None):
        super().__init__()
        self.field = field
        self.value = value
        self.rel = rel

    def __eq__(self, value):
        if isinstance(value, str):
            self.value = value
            self.rel = "isequalto"
            return self
        else:
            raise Exception

    def to_PHP_inner(self, **info):
        return {
            "type": "profile",
            "sf": self.field,
            "op": self.rel,
            "v": self.value
        }


class CondCompound(Cond):
    def __init__(self, sts=[]):
        super().__init__(sts)
        self.negate = False

    def __not__(self):
        self.negate = not self.negate
        return self

    def to_PHP(self, **info):
        e = self.to_PHP_inner(**info)
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
    def to_PHP_inner(self, **info):
        sts_PHP = [e.to_PHP_inner(**info) for e in self.sts]
        op = '!|' if self.negate else '|'
        return {'op': op, 'c': sts_PHP}


class CondAnd(CondCompound):
    def to_PHP_inner(self, **info):
        op = '!&' if self.negate else '&'
        sts_PHP = [e.to_PHP_inner(**info) for e in self.sts]
        return {'op': op, 'c': sts_PHP}
