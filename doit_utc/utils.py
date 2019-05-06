import pandas as pd
from datetime import timedelta

def aggregate(left_on, right_on, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
    def agregate0(df, path):
        if left_on not in df.columns:
            raise Exception("Pas de colonne %s dans le dataframe", left_on)
        if read_method is None:
            if path.endswith('.csv'):
                dff = pd.read_csv(path, **kw_read)
            elif path.endswith('.xlsx'):
                dff = pd.read_excel(path, **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            dff = read_method(path, **kw_read)

        if subset is not None:
            dff = dff[list(set([right_on] + subset))]
        if drop is not None:
            if right_on in drop:
                raise Exception('On enlève pas la clé')
            dff = dff.drop(drop, axis=1, errors='ignore')
        if rename is not None:
            if right_on in rename:
                raise Exception('Pas de renommage de la clé possible')
            dff = dff.rename(columns=rename)
        if right_on not in dff.columns:
            raise Exception("Pas de colonne %s dans le dataframe", right_on)
        df = df.merge(dff, left_on=left_on, right_on=right_on, suffixes=('', '_y'))
        drop_cols = [right_on + '_y']
        df = df.drop(drop_cols, axis=1, errors='ignore')
        return df
    return agregate0

def skip_range(d1, d2):
    return([d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)])

def skip_week(d1, weeks=1):
    return([d1 + timedelta(days=x) for x in range(7*weeks-1)])
