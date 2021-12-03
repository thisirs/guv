import re
import textwrap
from datetime import timedelta
from collections.abc import Callable
from typing import Optional, List, Union
import functools
import inspect

from schema import Schema, Or, And, Use
import pandas as pd

from .config import logger
from .utils import check_columns, check_filename, slugrot, slugrot_string
from .exceptions import ImproperlyConfigured


def fillna_column(
    colname: str, *, na_value: Optional[str] = None, group_column: Optional[str] = None
):
    """Remplace les valeurs non définies dans la colonne ``colname``.

    Une seule des options ``na_value`` et ``group_column`` doit être
    spécifiée. Si ``na_value`` est spécifiée, on remplace
    inconditionnellement par la valeur fournie. Si ``group_column`` est
    spécifiée, on complète en groupant par ``group_column`` et en prenant
    la seule valeur valide par groupe dans cette colonne.

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

    - Mettre les entrées non définies dans la colonne ``note`` à
      "ABS" :

      .. code:: python

         DOCS.fillna_column("note", na_value="ABS")

    - Mettre les entrées non définies à l'intérieur de chaque groupe
      repéré par la colonne ``groupe_projet`` à la seule valeur
      définie à l'intérieur de ce groupe.

      .. code:: python

         DOCS.fillna_column("note_projet", group_column="groupe_projet")

    """
    if not((na_value is None) ^ (group_column is None)):
        raise Exception("Une seule des options `na_value` et `group_column` doit être spécifiée")

    if na_value is not None:
        def func(df):
            check_columns(df, [colname])
            df[colname].fillna(na_value, inplace=True)
            return df

        func.__desc__ = f"Remplace les NA dans la colonne `{colname}` par la valeur `{na_value}`"

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

        def func(df):
            check_columns(df, [colname, group_column])
            return df.groupby(group_column).apply(fill_by_group)

        func.__desc__ = f"Remplace les NA dans la colonne `{colname}` en groupant par `{group_column}`"

    return func


def replace_column_aux(df, colname=None, new_column=None, backup=False, msg=None):
    """Helper function for `replace_regex` and `replace_column`."""

    if backup:
        df = df.assign(**{f"{colname}_orig": df[colname]})
        target_colname = colname
    elif new_colname is not None:
        target_colname = new_colname
    else:
        target_colname = colname

    df = df.assign(**{target_colname: new_column})

    return df


def replace_regex(
    colname: str,
    *reps,
    new_colname: Optional[str] = None,
    backup: Optional[bool] = False,
    msg: Optional[str] = None,
):
    """Remplacements regex dans une colonne.

    Remplace dans la colonne ``colname`` les occurrences de toutes les
    expressions régulières renseignées dans ``reps``.

    Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
    avant toute modification (avec un suffixe ``.orig``). Si
    l'argument ``new_colname`` est fourni la colonne est copiée vers
    une nouvelle colonne de nom ``new_colname`` et les modifications
    sont faites sur cette nouvelle colonnne.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où effectuer les remplacements
    *reps : any number of :obj:`tuple`
        Les couples regex / remplacement
    new_colname : :obj:`str`
        Le nom de la nouvelle colonne
    backup : :obj:`bool`
        Sauvegarder la colonne avant tout changement
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       DOCS.replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))

    """

    if backup is True and new_colname is not None:
        raise ImproperlyConfigured(
            "Les arguments `backup` et `new_colname` sont incompatibles."
        )

    def func(df):
        check_columns(df, colname)

        new_column = df[colname].copy()
        for rep in reps:
            new_column = new_column.str.replace(*rep, regex=True)

        return replace_column_aux(
            df, colname=colname, new_column=new_column, backup=backup, msg=msg
        )

    if msg is not None:
        func.__desc__ = msg
    elif new_colname is None:
        func.__desc__ = f"Remplacement regex dans colonne `{colname}`"
    else:
        func.__desc__ = f"Remplacement regex dans colonne `{colname} vers colonne `{new_colname}`"

    return func


def replace_column(
    colname: str,
    rep_dict: dict,
    new_colname: Optional[str] = None,
    backup: Optional[bool] = False,
    msg: Optional[str] = None,
):
    """Remplacements dans une colonne.

    Remplace les valeurs renseignées dans ``rep_dict`` dans la colonne
    ``colname``.

    Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
    avant toute modification (avec un suffixe ``.orig``). Si
    l'argument ``new_colname`` est fourni la colonne est copiée vers
    une nouvelle colonne de nom ``new_colname`` et les modifications
    sont faites sur cette nouvelle colonnne.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où effectuer les remplacements
    rep_dict : :obj:`dict`
        Dictionnaire des remplacements
    new_colname : :obj:`str`
        Nom de la nouvelle colonne
    backup : :obj:`bool`
        Sauvegarder la colonne avant tout changement
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       DOCS.replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})

    """

    if backup is True and new_colname is not None:
        raise ImproperlyConfigured(
            "Les arguments `backup` et `new_colname` sont incompatibles."
        )

    def func(df):
        check_columns(df, colname)
        new_column = df[colname].replace(rep_dict)
        return replace_column_aux(
            df, colname=colname, new_column=new_column, backup=backup, msg=msg
        )

    if msg is not None:
        func.__desc__ = msg
    elif new_colname is None:
        func.__desc__ = f"Remplacement dans colonne `{colname}`"
    else:
        func.__desc__ = f"Replacement dans colonne `{colname}` vers colonne `{new_colname}`"

    return func


def apply_df(func: Callable, msg: Optional[str] = None):
    """Modifie une colonne existante avec une fonction.

    ``func`` est une fonction prenant en argument un DataFrame et
    retournant le DataFrame modifié.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    func : :obj:`callable`
        Fonction prenant en argument un DataFrame et renvoyant un
        DataFrame modifié
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       DOCS.apply_df(
           lambda df: df.loc[~df["Adresse de courriel"].duplicated(), :],
           msg="Retirer les utilisateurs dupliqués"
       )

    """
    def func2(df):
        return func(df)

    if msg is not None:
        func2.__desc__ = msg
    else:
        func2.__desc__ = f"Appliquer une fonction au Dataframe"

    return func2


def apply_column(colname: str, func: Callable, msg: Optional[str] = None):
    """Modifie une colonne existance avec une fonction.

    ``colname`` est un nom de colonne existant et ``func`` une fonction
    prenant en argument un élément de la colonne et retournant un
    élément modifié.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    colname : :obj:`str`
        Nom de la colonne où effectuer les remplacements
    func : :obj:`callable`
        Fonction prenant en argument un élément et renvoyant l'élément
        modifié
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       DOCS.apply("note", lambda e: float(str(e).replace(",", ".")))

    """
    def func2(df):
        check_columns(df, colname)
        df.loc[:, colname] = df[colname].apply(func)
        return df

    if msg is not None:
        func2.__desc__ = msg
    else:
        func2.__desc__ = f"Appliquer une fonction à la colonne `{colname}`"

    return func2


def compute_new_column(*cols: str, func: Callable, colname: str, msg: Optional[str] = None):
    """Création d'une colonne à partir d'autres colonnes.

    Les colonnes nécessaires au calcul sont renseignées dans ``cols``.
    La fonction ``func`` qui calcule la nouvelle colonne reçoit une
    *Series* Pandas de toutes les valeurs contenues dans les colonnes
    spécifiées.

    Parameters
    ----------

    *cols : list of :obj:`str`
        Liste des colonnes fournies à la fonction ``func``
    func : :obj:`callable`
        Fonction prenant en argument un dictionnaire "nom des
        colonnes/valeurs" et renvoyant une valeur calculée
    colname : :obj:`str`
        Nom de la colonne à créer
    msg : :obj:`str`
        Un message descriptif utilisé

    Examples
    --------

    - Moyenne pondérée de deux notes :

      .. code:: python

         from guv.helpers import compute_new_column

         def moyenne(notes):
             return .4 * notes["Note_médian"] + .6 * notes["Note_final"]

         DOCS.compute_new_column("Note_médian", "Note_final", func=moyenne, colname="Note_moyenne")

    - Moyenne sans tenir compte des valeurs non définies :

      .. code:: python

         from guv.helpers import compute_new_column

         def moyenne(notes):
             return notes.mean()

         DOCS.compute_new_column("note1", "note2", "note3", func=moyenne, colname="Note_moyenne")

    """
    def func2(df):
        check_columns(df, cols)
        new_col = df.apply(lambda x: func(x.loc[list(cols)]), axis=1)
        df = df.assign(**{colname: new_col})
        return df

    if msg is not None:
        func2.__desc__ = msg
    else:
        func2.__desc__ = f"Calcul de la colonne `{colname}`"

    return func2


def aggregate_df(
    left_df,
    right_df,
    left_on,
    right_on,
    preprocessing=None,
    postprocessing=None,
    subset=None,
    drop=None,
    rename=None,
):
    """Merge two dataframes"""

    if preprocessing is not None:
        if hasattr(preprocessing, "__desc__"):
            logger.info(f"Preprocessing: {preprocessing.__desc__}")
        else:
            logger.info("Preprocessing")
        right_df = preprocessing(right_df)

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

    # Warn if right_on contains duplicates
    if any(right_df[right_on].duplicated()):
        logger.warning("La colonne `right_on` du fichier à agréger contient des clés identiques")

    # Extract subset of columns, right_on included
    if subset is not None:
        if isinstance(subset, str):
            subset = [subset]

        check_columns(right_df, subset)
        right_df = right_df[[right_on] + subset]

    # Allow to drop columns, right_on not allowed
    if drop is not None:
        if isinstance(drop, str):
            drop = [drop]

        if right_on in drop:
            raise Exception("Impossible d'enlever la clé")

        check_columns(right_df, drop)
        right_df = right_df.drop(drop, axis=1)

    # Rename columns in data to be merged
    if rename is not None:
        if right_on in rename:
            raise Exception("Pas de renommage de la clé possible")

        check_columns(right_df, rename.keys())
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
        logger.warning(f"Identifiant présent dans le document à aggréger mais introuvable dans la base de données : {row[key]}")

    if postprocessing is not None:
        def apply_postprocessing(df, func):
            if hasattr(func, "__desc__"):
                logger.info(f"Postprocessing: {func.__desc__}")
            else:
                logger.info("Postprocessing")
            return func(df)

        if not isinstance(postprocessing, tuple):
            postprocessing = (postprocessing,)

        for func in postprocessing:
            agg_df = apply_postprocessing(agg_df, func)

    # Try to merge columns
    for c in duplicated_columns:
        c_y = c + '_y'
        logger.warn("Fusion des colonnes `%s`" % c)
        if any(agg_df[c_y].notna() & agg_df[c].notna()):
            logger.warn("Fusion impossible")
            continue
        else:
            dtype = agg_df.loc[:, c].dtype
            agg_df.loc[:, c] = agg_df.loc[:, c].fillna(agg_df.loc[:, c_y])
            new_dtype = agg_df.loc[:, c].dtype
            if new_dtype != dtype:
                logger.warn(f"Le type de la colonne a changé suite à la fusion: {dtype} -> {new_dtype}")
                try:
                    logger.warn("Conversion de type")
                    agg_df.loc[:, c] = agg_df[c].astype(dtype)
                except ValueError:
                    logger.warn("Conversion impossible")
            drop_cols.append(c_y)

    # Drop useless columns
    agg_df = agg_df.drop(drop_cols, axis=1, errors='ignore')

    return agg_df


def aggregate(
    filename: str,
    *,
    left_on: Union[None, str, callable] = None,
    right_on: Union[None, str, callable] = None,
    on: Optional[str] = None,
    subset: Union[None, str, List[str]] = None,
    drop: Union[None, str, List[str]] = None,
    rename: Optional[dict] = None,
    preprocessing: Optional[Callable] = None,
    postprocessing: Optional[Callable] = None,
    read_method: Optional[Callable] = None,
    kw_read: Optional[dict] = {}
):
    """Agrégation d'un tableau provenant d'un fichier Excel/csv.

    Les arguments ``left_on`` et ``right_on`` sont les clés pour
    réaliser une jointure : ``left_on`` est la clé du DataFrame
    existant et ``right_on`` est la clé du DataFrame à agréger présent
    dans le fichier. ``left_on`` et ``right_on`` peuvent aussi être
    des callable prenant en argument le DataFrame correspondant et
    renvoyant une nouvelle colonne avec laquelle faire la jointure.
    Dans le cas où ``left_on`` et ``right_on`` ont la même valeur, on
    peut seulement spécifier ``on``.

    ``subset`` est une liste des colonnes à garder si on ne veut pas
    agréger la totalité des colonnes, ``drop`` une liste des colonnes
    à enlever. ``rename`` est un dictionnaire des colonnes à renommer.
    ``read_method`` est un callable appelé avec ``kw_read`` pour lire
    le fichier contenant le DataFrame à agréger. ``preprocessing`` et
    ``postprocessing`` sont des callable qui prennent en argument un
    DataFrame et en renvoie un et qui réalise un pré ou post
    traitement sur l'agrégation.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier csv/Excel à agréger.

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

    on : :obj:`str`
        Raccourci lorsque ``left_on`` et ``right_on`` ont la même
        valeur.

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

       DOCS.aggregate(
           "documents/notes.csv",
           left_on="Courriel",
           right_on="email"
       )

       from guv.utils import slugrot
       DOCS.aggregate(
           "documents/notes.csv",
           left_on=slugrot("Nom", "Prénom"),
           right_on=slugrot("Nom", "Prénom")
       )

    """

    def aggregate0(left_df):
        # Infer a read method if not provided
        if read_method is None:
            if filename.endswith('.csv'):
                right_df = pd.read_csv(filename, **kw_read)
            elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                right_df = pd.read_excel(filename, engine="openpyxl", **kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            right_df = read_method(filename, **kw_read)

        if on is not None:
            if left_on is not None or right_on is not None:
                raise ImproperlyConfigured("On doit spécifier soit `on`, soit `left_on` et `right_on`.")

            left_on_ = right_on_ = on
        else:
            left_on_ = left_on
            right_on_ = right_on

        return aggregate_df(
            left_df,
            right_df,
            left_on=left_on_,
            right_on=right_on_,
            preprocessing=preprocessing,
            postprocessing=postprocessing,
            subset=subset,
            drop=drop,
            rename=rename,
        )

    aggregate0.__desc__ = f"Agrégation du fichier `{filename}`"

    return aggregate0


def aggregate_org(
    filename: str,
    *,
    colname: str,
    on: Optional[str] = None,
    postprocessing: Optional[Callable] = None
):
    """Agrégation d'un fichier au format Org.

    Le document à agréger est au format Org. Les titres servent de clé
    pour l'agrégation et le contenu de ces titres et agréger.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier Org à agréger.

    colname : :obj:`str`
        Nom de la colonne dans lequel stocker les informations
        présentes dans le fichier Org.

    on : :obj:`str`, optional
        Colonne du fichier ``effectif.xlsx`` servant de clé pour
        agréger avec les titres du fichier Org. Par défaut, les titres
        doivent contenir les nom et prénom des étudiants.

    postprocessing : :obj:`callable`, optional
        Post-traitement à appliquer au `DataFrame` après intégration du fichier Org.

    Examples
    --------

    - Agrégation d'un fichier avec les noms des étudiants pour titre :

      Le fichier Org :

      .. code:: text

         * Bob Morane
           Souvent absent
         * Untel
           Voir email d'excuse

      L'instruction d'agrégation :

      .. code:: python

         DOCS.aggregate_org("documents/infos.org", colname="Informations")

    - Agrégation d'un fichier avec pour titres les éléments d'une
      colonne existante. Par exemple, on peut agréger les notes par
      groupe de projet prises dans le fichier Org. On spécifie la
      colonne contenant les groupes de projet "Projet1_Group".

      Le fichier Org :

      .. code:: text

         * Projet1_Group1
           A
         * Projet1_Group2
           B

      L'instruction d'agrégation :

      .. code:: python

         DOCS.aggregate_org("documents/infos.org", colname="Note projet 1", on="Project1_group")

    """

    def aggregate_org0(left_df):
        check_filename(filename)

        def parse_org(text):
            for chunk in re.split("^\\* *", text, flags=re.MULTILINE):
                if not chunk:
                    continue
                header, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                yield header, text

        text = open(filename, 'r').read()
        df_org = pd.DataFrame(parse_org(text), columns=["header", colname])

        if on is None:
            left_on = slugrot("Nom", "Prénom")
            right_on = slugrot("header")
        else:
            left_on = on
            right_on = "header"

        df = aggregate_df(left_df, df_org, left_on, right_on, postprocessing=postprocessing)
        return df

    aggregate_org0.__desc__ = f"Agrégation du fichier `{filename}`"

    return aggregate_org0


def flag(filename: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
    """Signaler une liste d'étudiants dans une nouvelle colonne.

    Le document à agréger est une liste de noms d'étudiants affichés
    ligne par ligne.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier à agréger.

    colname : :obj:`str`
        Nom de la colonne dans laquelle mettre la drapeau.

    flags : :obj:`str`, optional
        Les drapeaux utilisés, par défaut "Oui" et vide.

    Examples
    --------

    Agrégation d'un fichier avec les noms des étudiants pour titre :

    Le fichier "tiers_temps.txt" :

    .. code:: text

       Bob Morane

    L'instruction d'agrégation :

    .. code:: python

       DOCS.flag("documents/tiers_temps.txt", colname="Tiers-temps")

    """

    def func(df):
        check_filename(filename)
        check_columns(df, colname, error_when="exists")

        df[colname] = flags[1]

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        with open(filename, 'r') as fd:
            for line in fd:
                # Saute commentaire ou ligne vide
                line = line.strip()
                if line.startswith('#'):
                    continue
                if not line:
                    continue

                slugname = slugrot_string(line)

                res = df.loc[df.fullname_slug == slugname]
                if len(res) == 0:
                    raise Exception('Pas de correspondance pour `{:s}`'.format(line))
                elif len(res) > 1:
                    raise Exception('Plusieurs correspondances pour `{:s}`'.format(line))
                df.loc[res.index[0], colname] = flags[0]

        df = df.drop('fullname_slug', axis=1)
        return df

    func.__desc__ = f"Agrégation du fichier `{filename}`"

    return func


def apply_cell(name_or_email: str, colname: str, value):
    """Remplace la valeur d'une cellule.

    ``name_or_email`` est le nom de l'édudiant ou son adresse courriel
    et ``colname`` est le nom de la colonne où faire le changement. La
    nouvelle valeur est renseignée par ``value``.

    Parameters
    ----------

    name_or_email : :obj:`str`
        Le nom ou l'adresse courriel de l'étudiant.

    colname : :obj:`str`
        Le nom de la colonne où faire les modifications.

    value :
        La valeur à affecter.

    Examples
    --------

    .. code:: python

       DOCS.apply_cell("Mark Watney", "Note bricolage", 20)

    """

    def apply_cell_func(df):
        check_columns(df, columns=colname, error_when="not_found")

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        if '@etu' in name_or_email:
            sturow = df.loc[df['Courriel'] == name_or_email]
            if len(stu1row) > 1:
                raise Exception(f'Adresse courriel `{name_or_email}` présente plusieurs fois')
            if len(stu1row) == 0:
                raise Exception(f'Adresse courriel `{name_or_email}` non présente dans la base de données')
            stuidx = sturow.index[0]
        else:
            sturow = df.loc[df.fullname_slug == slugrot_string(name_or_email)]
            if len(sturow) > 1:
                raise Exception(f'Étudiant de nom `{name_or_email}` présent plusieurs fois')
            if len(sturow) == 0:
                raise Exception(f'Étudiant de nom `{name_or_email}` non présent dans la base de données')
            stuidx = sturow.index[0]

        df.loc[stuidx, colname] = value

        df = df.drop('fullname_slug', axis=1)
        return df

    apply_cell_func.__desc__ = f"Modification de la colonne `{colname}` pour l'identifiant `{name_or_email}`"

    return apply_cell_func


def switch(
    filename: str,
    *,
    colname: str,
    backup: bool = False,
    new_colname: Optional[str] = None
):
    """Réalise des échanges de valeurs dans une colonne.

    L'argument ``colname`` est la colonne dans laquelle opérer les
    échanges. Si l'argument ``backup`` est spécifié, la colonne est
    sauvegardée avant toute modification (avec un suffixe ``.orig``).
    Si l'argument ``new_colname`` est fourni la colonne est copiée
    vers une nouvelle colonne de nom ``new_colname`` et les
    modifications sont faites sur cette nouvelle colonnne.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier à agréger.
    colname : :obj:`str`
        Nom de la colonne où opérer les changements
    backup : :obj:`bool`
        Sauvegarder la colonne avant tout changement
    new_colname : :obj:`str`
        Le nom de la nouvelle colonne

    Examples
    --------

    .. code:: python

       DOCS.switch("fichier_échange_TP", colname="TP")

    """

    if backup is True and new_colname is not None:
        raise ImproperlyConfigured(
            "Les arguments `backup` et `new_colname` sont incompatibles."
        )

    def switch_func(df):
        """Apply switches in DataFrame `df`"""

        # Check that filename and column exist
        check_filename(filename)
        check_columns(df, columns=colname, error_when="not_found")

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
            logger.info(f"Échange de '{nom1}' et '{nom2}' dans la colonne '{col}'")

            tmp = df.loc[idx1, col]
            df.loc[idx1, col] = df.loc[idx2, col]
            df.loc[idx2, col] = tmp

        with open(filename, 'r') as fd:
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
                    logger.info(f"Étudiant(e) '{stu1}' affecté(e) au groupe '{stu2}'")
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

    switch_func.__desc__ = f"Agrégation du fichier `{filename}`"

    return switch_func


class Documents:
    def __init__(self):
        self._actions = []
        self._deps = []

    @property
    def deps(self):
        return self._deps

    def _add_dep(self, dep):
        self._deps.append(dep)

    def _add_action(self, func):
        self._actions.append(func)

    def add_documents(self, doc):
        for a in doc._actions:
            self._add_action(a)
        for d in doc._deps:
            self._add_dep(d)

    def apply_actions(self, df):
        for action in self._actions:
            logger.info(action.__desc__)
            df = action(df)
        return df

    def add(self, filename, func):
        """Déclare une agrégation d'un fichier à l'aide d'une fonction.

        Fonction générale pour déclarer l'agrégation d'un fichier de
        chemin ``filename`` à l'aide d'une fonction ``func`` prenant
        en argument le DataFrame déjà existant, le chemin vers le
        fichier et renvoie le DataFrame mis à jour.

        Voir fonctions spécialisées pour l'incorporation de documents
        classiques :

        - :func:`~guv.helpers.Documents.aggregate` : Document csv/Excel
        - :func:`~guv.helpers.Documents.aggregate_org` : Document Org

        Parameters
        ----------

        filename : :obj:`str`
            Le chemin du fichier à agréger.

        func : :obj:`callable`
            Une fonction de signature `DataFrame`, filename: str ->
            `DataFrame` qui réalise l'agrégation.

        Examples
        --------

        .. code:: python

           def fonction_qui_incorpore(df, file_path):
               # On incorpore le fichier dont le chemin est `file_path` au
               # DataFrame `df` et on renvoie le DataFrame mis à jour.

           DOCS.add("documents/notes.csv", func=fonction_qui_incorpore)

        """

        def func2(df):
            return func(df, filename)

        func2.__desc__ = f"Agrégation du fichier {filename}"
        self._add_action(func2)
        self._add_dep(filename)


def add_action_method(cls, func, file=False):
    """Add `func` as a method in class `cls`"""

    sig = inspect.Signature(
        (
            inspect.Parameter(name="self", kind=inspect.Parameter.POSITIONAL_ONLY),
            *tuple(inspect.signature(func).parameters.values()),
        )
    )

    @functools.wraps(func)
    def dummy(self, *args, **kwargs):
        action = func(*args, **kwargs)
        if file:
            self._add_dep(args[0])
        self._add_action(action)
        return self

    dummy.__signature__ = sig
    setattr(cls, func.__name__, dummy)


actions = [
    (fillna_column, {}),
    (replace_regex, {}),
    (replace_column, {}),
    (apply_cell, {}),
    (apply_column, {}),
    (apply_df, {}),
    (compute_new_column, {}),
    (flag, {"file": True}),
    (aggregate, {"file": True}),
    (aggregate_org, {"file": True}),
    (switch, {"file": True}),
]

for action, kwargs in actions:
    add_action_method(Documents, action, **kwargs)


def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]
