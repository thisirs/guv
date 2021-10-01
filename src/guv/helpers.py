import re
import textwrap
from datetime import timedelta
from schema import Schema, Or, And, Use
import pandas as pd

from .config import logger
from .utils import check_columns, slugrot, slugrot_string


def fillna_column(colname, na_value=None, group_column=None):
    """Renvoie une fonction qui remplace les valeurs non définies dans la colonne ``colname``.

    Une seule des options ``na_value`` et ``group_column`` doit être
    spécifiée. Si ``na_value`` est spécifiée, on remplace
    inconditionnellement par la valeur fournie. Si ``group_column`` est
    spécifiée, on complète en groupant par ``group_column`` en prenant
    la seule valeur valide par groupe dans cette colonne.

    Utilisable avec l'argument ``postprocessing`` ou ``preprocessing``
    dans la fonction ``aggregate`` ou directement à la place de la
    fonction ``aggregate`` dans ``AGGREGATE_DOCUMENTS``.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où remplacer les ``NA``
    na_value : :obj:`str`, optional
        Valeur remplaçant les valeurs non définies
    group_column : :obj:`str`, optional
        Nom de la colonne utilisée pour le groupement

    Examples
    --------

    .. code:: python

       from guv.helpers import fillna_column
       AGGREGATE_DOCUMENTS = [
           [None, fillna_column("group", na_value="ABS")],
           [None, fillna_column("group", group_column="choix")]
       ]

    """
    if not((na_value is None) ^ (group_column is None)):
        raise Exception("Une seule des options `na_value` et `group_column` doit être spécifiée")

    if na_value is not None:
        def func(df, path=None):
            check_columns(df, [colname])
            df[colname].fillna(na_value, inplace=True)
            return df

        func.__name__ = f"Remplace les NA dans la colonne `{colname}` par la valeur `{na_value}`"

    else:
        def fill_by_group(g):
            idx_first = g[colname].first_valid_index()
            idx_last = g[colname].last_valid_index()
            if idx_first is not None:
                if idx_first == idx_last:
                    g[colname] = g.loc[idx_first, colname]
                else:
                    logger.warning("Plusieurs valeurs non-NA dans le groupe")
                    print(g[["Nom", "Prénom", colname]])
            else:
                logger.warning("Aucune valeur non-NA dans le groupe")
            return g

        def func(df, path=None):
            check_columns(df, [colname, group_column])
            return df.groupby(group_column).apply(fill_by_group)

        func.__name__ = f"Remplace les NA dans la colonne `{colname}` en groupant par `{group_column}`"

    return func


def replace_regex(colname, *reps, new_colname=None, msg=None):
    """Renvoie une fonction qui remplace les occurrences de toutes les
    expressions régulières renseignées dans ``reps`` dans la colonne
    ``colname``.

    Utilisable avec l'argument ``postprocessing`` ou ``preprocessing``
    dans la fonction ``aggregate`` ou directement à la place de la
    fonction ``aggregate`` dans ``AGGREGATE_DOCUMENTS``.

    Si ``new_colname`` est spécifié, une nouvelle colonne est créée avec
    ce nom et ``colname`` est laissée. Sinon les valeurs sont
    directement remplacées dans le colonne ``colname``.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où effectuer les remplacements
    *reps :
        Les couples regex / remplacement
    new_colname : :obj:`str`
        Le nom de la nouvelle colonne
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       from guv.helpers import replace_regex
       AGGREGATE_DOCUMENTS = [
           [None, replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))]
       ]

    """

    def func(df, path=None):
        check_columns(df, colname)
        s = df[colname].copy()
        for rep in reps:
            s = s.str.replace(*rep, regex=True)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: s})
        return df

    if msg is not None:
        func.__name__ = msg
    elif new_colname is None:
        func.__name__ = f"Remplacement regex dans colonne `{colname}`"
    else:
        func.__name__ = f"Création colonne `{new_colname}` + replacement regex colonne `{colname}`"
    return func


def replace_column(colname, rep_dict, new_colname=None):
    """Renvoie une fonction qui remplace les valeurs exactes renseignées
    dans ``rep_dict`` dans la colonne ``colname``.

    Utilisable avec l'argument ``postprocessing`` ou ``preprocessing``
    dans la fonction ``aggregate`` ou directement à la place de la
    fonction ``aggregate`` dans ``AGGREGATE_DOCUMENTS``.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où effectuer les remplacements
    rep_dict : :obj:`dict`
        Dictionnaire des remplacements
    new_colname : :obj:`str`
        Nom de la nouvelle colonne

    Examples
    --------

    .. code:: python

       from guv.helpers import replace_column
       AGGREGATE_DOCUMENTS = [
           [None, replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})]
       ]

    """

    def func(df, path=None):
        check_columns(df, colname)
        col_ref = df[colname].replace(rep_dict)
        cn = new_colname if new_colname is not None else colname
        df = df.assign(**{cn: col_ref})
        return df

    func.__name__ = f"Replacements in column `{colname}`"

    return func


def compute_new_column(*cols, func=None, colname=None):
    """Renvoie une fonction qui calcule une nouvelle note à partir
    d'autres colonnes. Les colonnes utilisées sont renseignées dans
    ``cols``. La fonction ``func`` qui réalise l'agrégation reçoit une
    *Series* Pandas.

    Utilisable avec l'argument ``postprocessing`` ou ``preprocessing``
    dans la fonction ``aggregate`` ou directement à la place de la
    fonction ``aggregate`` dans ``AGGREGATE_DOCUMENTS``.

    Parameters
    ----------

    *cols
        Liste des colonnes fournies à la fonction ``func``
    func : :obj:`callable`
        Fonction prenant en argument un dictionnaire

    Examples
    --------

    .. code:: python

       from guv.helpers import compute_new_column

       def moyenne(notes):
           return (notes["Note_médian"] + notes["Note_final"]) / 2

       AGGREGATE_DOCUMENTS = [
           [
               None,
               compute_new_column(
                   "Note_médian", "Note_final", func=moyenne, colname="Note_moyenne"
               ),
           ]
       ]

    """
    if func is None:
        raise Exception("Fonction non spécifiée")
    if colname is None:
        raise Exception("Nom de colonne non spécifié")

    def func2(df, path=None):
        check_columns(df, cols)
        new_col = df.apply(lambda x: func(x.loc[list(cols)]), axis=1)
        df = df.assign(**{colname: new_col})
        return df

    func2.__name__ = f"Création colonne `{colname}`"

    return func2


def aggregate(left_on, right_on, preprocessing=None, postprocessing=None, subset=None, drop=None, rename=None, read_method=None, kw_read={}):
    """Renvoie une fonction qui réalise l'agrégation avec un fichier Excel/csv.

    Les arguments ``left_on`` et ``right_on`` sont les clés pour réaliser
    une jointure : ``left_on`` est la clé du DataFrame existant et
    ``right_on`` est la clé du DataFrame à agréger présent dans le
    fichier. ``left_on`` et ``right_on`` peuvent aussi être des callable
    prenant en argument le DataFrame correspondant et renvoyant une
    nouvelle colonne avec laquelle faire la jointure. ``subset`` est une
    liste des colonnes à garder, ``drop`` une liste des colonnes à
    enlever. ``rename`` est un dictionnaire des colonnes à renommer.
    ``read_method`` est un callable appelé avec ``kw_read`` pour lire le
    fichier contenant le DataFrame à agréger. ``preprocessing`` et
    ``postprocessing`` sont des callable qui prennent en argument un
    DataFrame et en renvoie un et qui réalise un pré ou post
    traitement sur l'agrégation.

    Parameters
    ----------

    left_on : :obj:`str`
        Le nom de colonne présent dans le fichier ``effectif.xlsx``
        pour réaliser la jointure. Au cas où la colonne n'existe pas,
        on peut spécifier une fonction prenant en argument le
        *DataFrame* et renvoyant une *Series* utilisée pour la
        jointure (voir fonction :func:`guv.utils.slugrot`).

    right_on : :obj:`str`
        Le nom de colonne présent dans le fichier à incorporer pour
        réaliser la jointure. Au cas où la colonne n'existe pas,
        on peut spécifier une fonction prenant en argument le
        *DataFrame* et renvoyant une *Series* utilisée pour la
        jointure (voir fonction :func:`guv.utils.slugrot`).

    subset : :obj:`list`, optional
        Permet de sélectionner un nombre restreint de colonnes en
        spécifiant la liste. Par défaut, toutes les colonnes sont
        incorporées.

    drop : :obj:`list`, optional
        Permet d'enlever des colonnes de l'agrégation.

    rename : :obj:`dict`, optional
        Permet de renommer des colonnes après incorporation.

    read_method : :obj:`callable`, optional
        Spécifie la fonction à appeler pour charger le fichier. Les
        fonctions Pandas ``pd.read_csv`` et ``pd.read_excel`` sont
        automatiquement sélectionnées pour les fichiers ayant pour
        extension ".csv" ou ".xlsx".

    kw_read : :obj:`dict`, optional
        Les arguments nommés à utiliser avec la fonction
        ``read_method``. Par exemple, pour un fichier ".csv" on peut
        spécifier :

        .. code:: python

           kw_read={"header": None, "names": ["Courriel", "TP_pres"]}
           kw_read={"na_values": "-"},

    preprocessing : :obj:`callable`, optional
        Pré-traitement à appliquer au `DataFrame` avant de l'intégrer.

    postprocessing : :obj:`callable`, optional
        Post-traitement à appliquer au `DataFrame` après intégration du fichier.

    Examples
    --------

    .. code:: python

       from guv.helpers import aggregate
       from guv.utils import slugrot
       AGGREGATE_DOCUMENTS = [
           [
               "documents/notes.csv",
               aggregate(
                   left_on="Courriel",
                   right_on="email"
               )
           ],
           [
               "documents/notes.csv",
               aggregate(
                   left_on=slugrot("Nom", "Prénom"),
                   right_on=slugrot("Nom", "Prénom")
               )
           ]
       ]

    """

    def aggregate0(left_df, path):
        nonlocal left_on, right_on, subset, drop, rename

        # Columns that will be removed after merging
        drop_cols = []

        # Flag if left_on is a computed column
        left_on_is_added = False

        # Add column if callable, callable should return of pandas
        # Series
        if callable(left_on):
            left_on = left_on(left_df)
            left_df = left_df.assign(**{left_on.name: left_on.values})
            left_on = left_on.name
            left_on_is_added = True

        # Check if it exists
        if isinstance(left_on, str):
            # Check that left_on column exists
            check_columns(left_df, left_on)
        else:
            raise Exception("L'argument 'left_on' doit être un callable ou une chaine de caractères")

        # Infer a read method if not provided
        if read_method is None:
            if path.endswith('.csv'):
                right_df = pd.read_csv(path, **kw_read)
            elif path.endswith('.xlsx') or path.endswith('.xls'):
                right_df = pd.read_excel(path, engine="openpyxl", **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            right_df = read_method(path, **kw_read)

        if preprocessing is not None:
            if hasattr(preprocessing, "__name__"):
                print(f"Preprocessing: {preprocessing.__name__}")
            else:
                print("Preprocessing")
            right_df = preprocessing(right_df)

        # Add column if callable
        if callable(right_on):
            right_on = right_on(right_df)
            right_df = right_df.assign(**{right_on.name: right_on.values})
            right_on = right_on.name

        # Check if it exists
        if isinstance(right_on, str):
            check_columns(right_df, right_on)
        else:
            raise Exception("Unsupported type for right_on")

        # Extract subset of columns, right_on included
        if subset is not None:
            sc_columns = Or(*right_df.columns)
            subset = Schema(Or(And(sc_columns, Use(lambda x: [x])), [sc_columns])).validate(subset)
            subset0 = list({s: 1 for s in [right_on] + subset}.keys())
            right_df = right_df[subset0]

        # Allow to drop columns, right_on not allowed
        if drop is not None:
            sc_columns = Or(*right_df.columns)
            drop = Schema(Or(And(sc_columns, Use(lambda x: [x])), [sc_columns])).validate(drop)
            if right_on in drop:
                raise Exception('On enlève pas la clé')
            right_df = right_df.drop(drop, axis=1)

        # Rename columns in data to be merged
        if rename is not None:
            if right_on in rename:
                raise Exception('Pas de renommage de la clé possible')
            rename = Schema({str: str}).validate(rename)
            right_df = right_df.rename(columns=rename)

        # Columns to drop after merge: primary key of right dataframe
        # only if name is different, _merge column added by pandas
        # during merge, programmatically added column is
        # left_on_is_added is set
        drop_cols = ['_merge']
        if right_on != left_on:
            if right_on in left_df.columns:
                drop_cols += [right_on + "_y"]
            else:
                drop_cols += [right_on]

        if left_on_is_added:
            drop_cols += [left_on]

        # Record same column name between right_df and left_df to
        # merge them eventually
        duplicated_columns = set(left_df.columns).intersection(set(right_df.columns))
        duplicated_columns = duplicated_columns.difference(set([left_on, right_on]))

        # Outer merge
        merged_df = left_df.merge(right_df,
                                  left_on=left_on,
                                  right_on=right_on,
                                  how='outer',
                                  suffixes=('', '_y'),
                                  indicator=True)

        # Select like how='left' as result
        agg_df = merged_df[merged_df["_merge"].isin(['left_only', 'both'])]

        # Select right only and report
        merged_df_ro = merged_df[merged_df["_merge"] == 'right_only']
        key = right_on
        if (right_on != left_on and right_on in left_df.columns):
            key = key + "_y"

        for index, row in merged_df_ro.iterrows():
            print("WARNING: identifiant présent dans le document à aggréger mais introuvable dans la base de données :", row[key])

        if postprocessing is not None:
            if hasattr(postprocessing, "__name__"):
                print(f"Postprocessing: {postprocessing.__name__}")
            else:
                print("Postprocessing")
            agg_df = postprocessing(agg_df)

        # Try to merge columns
        for c in duplicated_columns:
            c_y = c + '_y'
            print("Trying to merge columns '%s' and '%s'..." % (c, c_y), end='')
            if any(agg_df[c_y].notna() & agg_df[c].notna()):
                print('failed')
                continue
            else:
                agg_df.loc[:, c] = agg_df.loc[:, c].fillna(agg_df.loc[:, c_y])
                drop_cols.append(c_y)
                print('done')

        # Drop useless columns
        agg_df = agg_df.drop(drop_cols, axis=1, errors='ignore')

        return agg_df

    return aggregate0


def aggregate_org(colname, postprocessing=None):
    """Renvoie une fonction d'agrégation d'un fichier Org.

    Le document à agréger est au format Org avec un nom d'étudiant par
    headline.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne dans lequel stocker les informations
        présentes dans le fichier Org.

    postprocessing : :obj:`callable`, optional
        Post-traitement à appliquer au `DataFrame` après intégration du fichier Org.


    Examples
    --------

    Le fichier Org :

    .. code:: text

       * Bob Morane
         Souvent absent
       * Untel
         Voir email d'excuse


    L'instruction d'agrégation :

    .. code:: python

       from guv.helpers import aggregate_org
       AGGREGATE_DOCUMENTS = [
           ["documents/infos.org", aggregate_org("Informations")],
       ]

    """

    def aggregate_org0(left_df, path):
        if not path.endswith('.org'):
            raise Exception(f"{path} n'est pas un fichier org")

        left_df[colname] = ""

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        left_df["fullname_slug"] = tf_df(left_df)

        infos = open(path, 'r').read()
        if infos:
            for chunk in re.split("^\\* *", infos, flags=re.MULTILINE):
                if not chunk:
                    continue
                etu, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                slugname = slugrot_string(etu)

                res = left_df.loc[left_df.fullname_slug == slugname]
                if len(res) == 0:
                    raise Exception('Pas de correspondance pour `{:s}`'.format(etu))
                elif len(res) > 1:
                    raise Exception('Plusieurs correspondances pour `{:s}`'.format(etu))

                left_df.loc[res.index[0], colname] = text

        df = left_df.drop('fullname_slug', axis=1)

        if postprocessing is not None:
            if hasattr(postprocessing, "__name__"):
                print(f"Postprocessing: {postprocessing.__name__}")
            else:
                print("Postprocessing")

            df = postprocessing(df)

        return df
    return aggregate_org0


def switch(colname, backup=False, path=None, new_colname=None):
    """Renvoie une fonction qui réalise des échanges dans une colonne.

    L'argument ``colname`` est la colonne dans laquelle opérer les
    échanges. L'argument ``backup`` spécifie si la colonne doit être
    sauvegardée (avec un suffixe ``.orig``) avant de faire les
    échanges.

    Utilisable avec l'argument ``postprocessing`` ou ``preprocessing``
    dans la fonction ``aggregate`` en spécifiant l'argument ``path`` ou
    directement à la place de la fonction ``aggregate`` dans
    ``AGGREGATE_DOCUMENTS``.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où opérer les changements
    backup : :obj:`bool`
        Sauvegarder la colonne avant tout changement
    path : :obj:`str`
        Chemin de fichier lorsque ``switch`` est utilisée dans un
        argument ``postprocessing``.

    Examples
    --------

    .. code:: python

       from guv.helpers import switch
       AGGREGATE_DOCUMENTS = [
           ["fichier_échange_TP", switch("TP")]
       ]
       AGGREGATE_DOCUMENTS = [
           [
               "fichier_à_agréger",
               aggregate(..., postprocessing=switch("TP", path="fichier_échange_TP")),
           ]
       ]

    """

    if backup is True and new_colname is not None:
        raise Exception("Il faut soit un backup de la colonne (avec suffixe _orig), soit un nouveau nom de colonne")

    def switch_func(df, agg_path):
        """Apply switches specified in `fn` in DataFrame `df`"""

        if path is None and agg_path is None:
            raise Exception("Il faut spécifier un chemin avec l'argument `path` ou dans `AGGREGATE_DOCUMENTS`.")

        if agg_path is None:
            agg_path = path

        # Check that column exists
        check_columns(df, columns=[colname])

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        if backup:
            df[f'{colname}_orig'] = df[colname]
            target_colname = colname
        elif new_colname is not None:
            df[new_colname] = df[colname]
            target_colname = new_colname
        else:
            target_colname = colname

        names = df[target_colname].unique()

        def swap_record(df, idx1, idx2, col):
            nom1 = " ".join(df.loc[idx1, ["Nom", "Prénom"]])
            nom2 = " ".join(df.loc[idx2, ["Nom", "Prénom"]])
            logger.warning(f"Swapping '{nom1}' and '{nom2}' in column '{col}'")

            tmp = df.loc[idx1, col]
            df.loc[idx1, col] = df.loc[idx2, col]
            df.loc[idx2, col] = tmp

        with open(agg_path, 'r') as fd:
            for line in fd:
                if line.strip().startswith('#'):
                    continue
                if not line.strip():
                    continue

                try:
                    stu1, stu2, = [e.strip() for e in line.split('---')]
                except ValueError:
                    raise Exception(f"Ligne incorrecte: `{line.strip()}`")
                if not stu1 or not stu2:
                    raise Exception(f"Ligne incorrecte: `{line.strip()}`")

                # Indice de l'étudiant 1
                if '@etu' in stu1:
                    stu1row = df.loc[df['Courriel'] == stu1]
                    if len(stu1row) != 1:
                        raise Exception(f'Adresse courriel `{stu1}` non présente dans la base de données')
                    stu1idx = stu1row.index[0]
                else:
                    stu1row = df.loc[df.fullname_slug == slugrot_string(stu1)]
                    if len(stu1row) != 1:
                        raise Exception(f'Étudiant de nom `{stu1}` non présent ou reconnu dans la base de données')
                    stu1idx = stu1row.index[0]

                if stu2 in names: # Le deuxième élément est une colonne
                    logger.warning(f"Étudiant(e) '{stu1}' affecté(e) au groupe '{stu2}'")
                    df.loc[stu1idx, target_colname] = stu2
                elif '@etu' in stu2: # Le deuxième élément est une adresse email
                    stu2row = df.loc[df['Courriel'] == stu2]
                    if len(stu2row) != 1:
                        raise Exception(f'Adresse courriel `{stu2}` non présente dans la base de données')
                    stu2idx = stu2row.index[0]
                    swap_record(df, stu1idx, stu2idx, target_colname)
                else:
                    stu2row = df.loc[df.fullname_slug == slugrot_string(stu2)]
                    if len(stu2row) != 1:
                        raise Exception(f'Étudiant ou nom de séance `{stu2}` non reconnu dans la base de données')
                    stu2idx = stu2row.index[0]
                    swap_record(df, stu1idx, stu2idx, target_colname)

        df = df.drop('fullname_slug', axis=1)
        return df

    return switch_func


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]
