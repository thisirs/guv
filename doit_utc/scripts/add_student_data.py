import re
import unidecode
import pandas as pd


def add_moodle_data(df, fn):
    """Incorpore les données du fichier extrait de Moodle"""

    if fn.endswith('.csv'):
        dfm = pd.read_csv(fn)
    elif fn.endswith('.xlsx') or fn.endswith('.xls'):
        dfm = pd.read_excel(fn)

    dfm = dfm.drop(['Institution', 'Département', 'Dernier téléchargement depuis ce cours'], axis=1)

    if 'Courriel' in df.columns:
        dfr = pd.merge(df, dfm,
                       suffixes=('', '_moodle'),
                       how='outer',
                       left_on='Courriel',
                       right_on='Adresse de courriel',
                       indicator=True)

        dfr_clean = dfr.loc[dfr['_merge'] == 'both']

        lo = dfr.loc[dfr['_merge'] == 'left_only']
        for index, row in lo.iterrows():
            fullname = row['Nom'] + ' ' + row['Prénom']
            print(f'add_moodle_data: {fullname} not in Moodle data')

        ro = dfr.loc[dfr['_merge'] == 'right_only']
        for index, row in ro.iterrows():
            fullname = row['Nom_moodle'] + ' ' + row['Prénom_moodle']
            print(f'add_moodle_data: {fullname} only in Moodle data')

        dfr = dfr.drop('_merge', axis=1)
        dfr = dfr.loc[~pd.isnull(dfr.Nom)]

    elif 'Name' in df.columns:
        fullnames = dfm['Nom'] + ' ' + dfm['Prénom']
        def slug(e):
            return unidecode.unidecode(e.upper()[:23].strip())
        fullnames = fullnames.apply(slug)
        dfm['fullname_slug'] = fullnames

        dfr = pd.merge(df, dfm,
                       how='outer',
                       left_on='Name',
                       right_on='fullname_slug',
                       indicator=True)

        lo = dfr.loc[dfr['_merge'] == 'left_only']
        for index, row in lo.iterrows():
            fullname = row['Name']
            print(f'add_moodle_data: {fullname} not in Moodle data')

        ro = dfr.loc[dfr['_merge'] == 'right_only']
        for index, row in ro.iterrows():
            fullname = row['Nom'] + ' ' + row['Prénom']
            print(f'add_moodle_data: {fullname} only in Moodle data')

    else:
        raise Exception('Pas de colonne Courriel ou Nom, Prénom')

    # Trying to merge manually lo and ro
    for index, row in lo.iterrows():
        fullname = row['Nom'] + ' ' + row['Prénom']
        print(f'Trying to find a match for {fullname}')
        for i, (index_ro, row_ro) in enumerate(ro.iterrows()):
            fullname_ro = row_ro['Nom_moodle'] + ' ' + row_ro['Prénom_moodle']
            print(f'({i}) {fullname_ro}')
        while True:
            try:
                choice = input('Your choice? (enter if no match) ')
                if choice and int(choice) not in range(len(ro.index)):
                    raise ValueError
            except ValueError:
                print('Value error')
                continue
            else:
                break

        if choice:
            row_merge = lo.loc[index, :].combine_first(ro.iloc[int(choice), :])
            row_merge['_merge'] = 'both'
            dfr_clean = dfr_clean.append(row_merge)

    dfr_clean = dfr_clean.drop('_merge', axis=1)

    return dfr_clean


def add_UTC_data(df, fn):
    'Incorpore les données Cours/TD/TP des inscrits UTC'

    # Données issues du fichier inscrits.raw
    dfu = pd.read_csv(fn)

    if 'Nom' in df.columns and 'Prénom' in df.columns:
        fullnames = df['Nom'] + ' ' + df['Prénom']
        def slug(e):
            return unidecode.unidecode(e.upper()[:23].strip())
        df['fullname_slug'] = fullnames.apply(slug)

        dfr = pd.merge(df, dfu,
                       suffixes=('', '_utc'),
                       how='outer',
                       left_on=['fullname_slug', 'Branche', 'Semestre'],
                       right_on=['Name', 'Branche', 'Semestre'],
                       indicator=True)

    else:
        raise Exception('')

    dfr_clean = dfr.loc[dfr['_merge'] == 'both']

    lo = dfr.loc[dfr['_merge'] == 'left_only']
    for index, row in lo.iterrows():
        key = row["fullname_slug"]
        branch = row["Branche"]
        semester = row["Semestre"]
        print(f'(`{key}`, `{branch}`, `{semester}`) not in UTC data')

    ro = dfr.loc[dfr['_merge'] == 'right_only']
    for index, row in ro.iterrows():
        key = row["Name"]
        branch = row["Branche"]
        semester = row["Semestre"]
        print(f'(`{key}`, `{branch}`, `{semester}`) only in UTC data')

    # Trying to merge manually lo and ro
    for index, row in lo.iterrows():
        fullname = row['Nom'] + ' ' + row['Prénom']
        print(f'Trying to find a match for {fullname}')
        for i, (index_ro, row_ro) in enumerate(ro.iterrows()):
            fullname_ro = row_ro['Name']
            print(f'({i}) {fullname_ro}')
        while True:
            try:
                choice = input('Your choice? (enter if no match) ')
                if choice and int(choice) not in range(len(ro.index)):
                    raise ValueError
            except ValueError:
                print('Value error')
                continue
            else:
                break

        if choice:
            row_merge = lo.loc[index, :].combine_first(ro.iloc[int(choice), :])
            row_merge['_merge'] = 'both'
            dfr_clean = dfr_clean.append(row_merge)

    dfr_clean = dfr_clean.drop(['_merge', 'fullname_slug'], axis=1)

    return dfr_clean


def filter_student(df, pattern):
    if '@' in pattern:
        pass
    else:
        pass


def add_tiers_temps(df, fn):
    # Aucun tiers-temps
    df['Tiers-temps'] = False

    def slug(e):
        return unidecode.unidecode(e.upper().strip())

    fullnames = df['Nom'] + ' ' + df['Prénom']
    fullnames = fullnames.apply(slug)
    df['fullname_slug'] = fullnames

    with open(fn, 'r') as fd:
        for line in fd:
            # Saute commentaire ou ligne vide
            line = line.strip()
            if line.startswith('#'):
                continue
            if not line:
                continue

            slugname = slug(line)

            res = df.loc[df.fullname_slug == slugname]
            if len(res) == 0:
                raise Exception('Pas de correspondance pour `{:s}`'.format(line))
            elif len(res) > 1:
                raise Exception('Plusieurs correspondances pour `{:s}`'.format(line))
            df.loc[res.index[0], 'Tiers-temps'] = True

    df = df.drop('fullname_slug', axis=1)
    return df


def add_switches(df, fn, ctype):
    def slug(e):
        return unidecode.unidecode(e.upper().strip())

    def swap_record(df, idx1, idx2, col):

        tmp = df.loc[idx1, col]
        df.loc[idx1, col] = df.loc[idx2, col]
        df.loc[idx2, col] = tmp

    fullnames = df['Prénom'] + ' ' + df['Nom']
    fullnames = fullnames.apply(slug)
    df['fullname_slug'] = fullnames
    df[f'{ctype}_orig'] = df[ctype]

    with open(fn, 'r') as fd:
        for line in fd:
            if line.strip().startswith('#'):
                continue
            if not line.strip():
                continue

            stu1, stu2, *t = [e.strip() for e in line.split('---')]
            assert len(t) == 0

            if '@etu' in stu1:
                stu1row = df.loc[df['Courriel'] == stu1]
                if len(stu1row) != 1:
                    raise Exception('Nombre d\'enregistrement != 1', len(stu1row), stu1)
                stu1idx = stu1row.index[0]
            else:
                stu1row = df.loc[df.fullname_slug == slug(stu1)]
                if len(stu1row) != 1:
                    raise Exception('Nombre d\'enregistrement != 1', len(stu1row), stu1)
                stu1idx = stu1row.index[0]

            if re.match('^[TD][0-9]+', stu2):
                df.loc[stu1idx, ctype] = stu2
            elif '@etu' in stu2:
                stu2row = df.loc[df['Courriel'] == stu2]
                if len(stu2row) != 1:
                    raise Exception('Nombre d\'enregistrement != 1', len(stu2row), stu2)
                stu2idx = stu2row.index[0]
                swap_record(df, stu1idx, stu2idx, ctype)
            else:
                stu2row = df.loc[df.fullname_slug == slug(stu2)]
                if len(stu2row) != 1:
                    raise Exception('Nombre d\'enregistrement != 1', len(stu2row), stu2)
                stu2idx = stu2row.index[0]
                swap_record(df, stu1idx, stu2idx, ctype)

    df = df.drop('fullname_slug', axis=1)
    return df


def add_student_info(df, fn):
    df['Info'] = ""

    def slug(e):
        return unidecode.unidecode(e.upper().strip())

    fullnames = df['Prénom'] + ' ' + df['Nom']
    fullnames = fullnames.apply(slug)
    df['fullname_slug'] = fullnames

    infos = open(fn, 'r').read()
    if infos:
        for chunk in re.split("^\\* *", infos, flags=re.MULTILINE):
            if not chunk:
                continue

            etu, *text = chunk.split("\n", maxsplit=2)
            text = "\n".join(text).strip("\n")
            slugname = slug(etu)

            res = df.loc[df.fullname_slug == slugname]
            if len(res) == 0:
                raise Exception('Pas de correspondance pour `{:s}`'.format(etu))
            elif len(res) > 1:
                raise Exception('Plusieurs correspondances pour `{:s}`'.format(etu))

            df.loc[res.index[0], 'Info'] = text

    df = df.drop('fullname_slug', axis=1)
    return df
