import copy
import functools
import os
import re
import textwrap
from collections.abc import Callable
from datetime import timedelta
from typing import List, Optional, Union
import zipfile

import numpy as np
import pandas as pd

from .aggregator import Aggregator, ColumnsMerger
from .config import settings
from .exceptions import ImproperlyConfigured
from .logger import logger
from .operation import Operation
from .utils import slugrot_string
from .utils_config import (check_filename, check_if_absent, check_if_present,
                           rel_to_dir)


def slugrot(*columns):
    "Rotation-invariant hash function on a dataframe"

    def func(df):
        check_if_present(df, columns)
        s = df[list(columns)].apply(
            lambda x: "".join(x.astype(str)),
            axis=1
        )

        s = s.apply(slugrot_string)
        s.name = "guv_" + "_".join(columns)
        return s

    return func


def make_concat(*columns):
    def func(df):
        check_if_present(df, columns)
        s = df[list(columns)].apply(
            lambda x: "".join(x.astype(str)),
            axis=1
        )

        s.name = "guv_" + "_".join(columns)
        return s

    return func


def concat(*columns):
    return ColumnsMerger(*columns, func=make_concat(*columns))


def id_slug(*columns):
    return ColumnsMerger(*columns, func=slugrot(*columns))


class FillnaColumn(Operation):
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

    def __init__(
        self,
        colname: str,
        *,
        na_value: Optional[str] = None,
        group_column: Optional[str] = None
    ):
        super().__init__()
        self.colname = colname
        self.na_value = na_value
        self.group_column = group_column

    def apply(self, df):
        if not((self.na_value is None) ^ (self.group_column is None)):
            raise Exception("Une seule des options `na_value` et `group_column` doit être spécifiée")

        if self.na_value is not None:
            check_if_present(df, self.colname)
            with pd.option_context('mode.chained_assignment', None):
                df.loc[:, self.colname] = df[self.colname].fillna(self.na_value)
        else:
            def fill_by_group(g):
                if not isinstance(g.name, str):
                    logger.warning("La colonne `%s` contient des entrées vides", self.group_column)
                    return g

                valid = g[self.colname].dropna()

                if len(valid) == 0:
                    logger.warning("Aucune valeur non-NA dans le groupe `%s`", g.name)
                elif len(valid) == 1:
                    g[self.colname] = valid.iloc[0]
                else:
                    all_equal = (valid == valid.iloc[0]).all()
                    if all_equal:
                        g[self.colname] = valid.iloc[0]
                    else:
                        logger.warning("Plusieurs valeurs non-NA et différentes dans le groupe `%s`", g.name)

                return g

            check_if_present(df, [self.colname, self.group_column])
            df = df.groupby(self.group_column, dropna=False, group_keys=False).apply(fill_by_group)

        return df

    def message(self, **kwargs):
        if self.na_value is not None:
            return f"Remplace les NA dans la colonne `{self.colname}` par la valeur `{self.na_value}`"

        return f"Remplace les NA dans la colonne `{self.colname}` en groupant par `{self.group_column}`"


class ReplaceRegex(Operation):
    """Remplacements regex dans une colonne.

    Remplace dans la colonne ``colname`` les occurrences de toutes les
    expressions régulières renseignées dans ``reps``.

    Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
    avant toute modification (avec un suffixe ``_orig``). Si
    l'argument ``new_colname`` est fourni la colonne est copiée vers
    une nouvelle colonne de nom ``new_colname`` et les modifications
    sont faites sur cette nouvelle colonne.

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
        Un message décrivant l'opération

    Examples
    --------

    .. code:: python

       DOCS.replace_regex("group", (r"group([0-9])", r"G\1"), (r"g([0-9])", r"G\1"))

    """

    def __init__(
        self,
        colname: str,
        *reps,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        super().__init__()
        self.colname = colname
        self.reps = reps
        self.new_colname = new_colname
        self.backup = backup
        self.msg = msg

    def apply(self, df):
        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                "Les arguments `backup` et `new_colname` sont incompatibles."
            )

        check_if_present(df, self.colname)

        new_column = df[self.colname].copy()
        for rep in self.reps:
            new_column = new_column.str.replace(*rep, regex=True)

        return replace_column_aux(
            df,
            new_colname=self.new_colname,
            colname=self.colname,
            new_column=new_column,
            backup=self.backup,
        )

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg
        if self.new_colname is None:
            return f"Remplacement regex dans colonne `{self.colname}`"

        return f"Remplacement regex dans colonne `{self.colname}` vers colonne `{self.new_colname}`"


class ReplaceColumn(Operation):
    """Remplacements dans une colonne.

    Remplace les valeurs renseignées dans ``rep_dict`` dans la colonne
    ``colname``.

    Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
    avant toute modification (avec un suffixe ``_orig``). Si
    l'argument ``new_colname`` est fourni la colonne est copiée vers
    une nouvelle colonne de nom ``new_colname`` et les modifications
    sont faites sur cette nouvelle colonne.

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
        Un message décrivant l'opération

    Examples
    --------

    .. code:: python

       DOCS.replace_column("group", {"TD 1": "TD1", "TD 2": "TD2"})

    .. code:: python

       ECTS_TO_NUM = {
           "A": 5,
           "B": 4,
           "C": 3,
           "D": 2,
           "E": 1,
           "F": 0
       }
       DOCS.replace_column("Note_TP", ECTS_TO_NUM, backup=True)

    """

    def __init__(
        self,
        colname: str,
        rep_dict: dict,
        new_colname: Optional[str] = None,
        backup: Optional[bool] = False,
        msg: Optional[str] = None,
    ):
        super().__init__()
        self.colname = colname
        self.rep_dict = rep_dict
        self.new_colname = new_colname
        self.backup = backup
        self.msg = msg

    def apply(self, df):
        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                "Les arguments `backup` et `new_colname` sont incompatibles."
            )

        check_if_present(df, self.colname)
        new_column = df[self.colname].replace(self.rep_dict)
        return replace_column_aux(
            df,
            new_colname=self.new_colname,
            colname=self.colname,
            new_column=new_column,
            backup=self.backup,
        )

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg
        if self.new_colname is None:
            return f"Remplacement dans colonne `{self.colname}`"

        return f"Replacement dans colonne `{self.colname}` vers colonne `{self.new_colname}`"


class ApplyDf(Operation):
    """Modifie le fichier central avec une fonction.

    ``func`` est une fonction prenant en argument un *DataFrame*
    représentant le fichier central et retournant le *DataFrame*
    modifié.

    Un message ``msg`` peut être spécifié pour décrire ce que fait la
    fonction, il sera affiché lorsque l'agrégation sera effectuée.
    Sinon, un message générique sera affiché.

    Parameters
    ----------

    func : :obj:`callable`
        Fonction prenant en argument un *DataFrame* et renvoyant un
        *DataFrame* modifié
    msg : :obj:`str`
        Un message décrivant l'opération

    Examples
    --------

    - Rajouter un étudiant absent de l'effectif officiel :

      .. code:: python

         import pandas as pd

         df_one = (
             pd.DataFrame(
                 {
                     "Nom": ["NICHOLS"],
                     "Prénom": ["Juliette"],
                     "Courriel": ["juliette.nichols@silo18.fr"],
                 }
             ),
         )

         DOCS.apply_df(lambda df: pd.concat((df, df_one)))

    - Retirer les étudiants dupliqués :

      .. code:: python

         DOCS.apply_df(
             lambda df: df.loc[~df["Adresse de courriel"].duplicated(), :],
             msg="Retirer les étudiants dupliqués"
         )

    """

    def __init__(self, func: Callable, msg: Optional[str] = None):
        super().__init__()
        self.func = func
        self.msg = msg

    def apply(self, df):
        return self.func(df)

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg

        return "Appliquer une fonction au Dataframe"


class ApplyColumn(Operation):
    """Modifie une colonne existante avec une fonction.

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
        Un message décrivant l'opération

    Examples
    --------

    .. code:: python

       DOCS.apply("note", lambda e: float(str(e).replace(",", ".")))

    """

    def __init__(self, colname: str, func: Callable, msg: Optional[str] = None):
        super().__init__()
        self.colname = colname
        self.func = func
        self.msg = msg

    def apply(self, df):
        check_if_present(df, self.colname)
        df.loc[:, self.colname] = df[self.colname].apply(self.func)
        return df

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg

        return f"Appliquer une fonction à la colonne `{self.colname}`"


class ComputeNewColumn(Operation):
    """Création d'une colonne à partir d'autres colonnes.

    Les colonnes nécessaires au calcul sont renseignées dans ``cols``.
    Au cas où, on voudrait changer la colonne utilisée pour le calcul
    sans changer la fonction ``func``, il est possible de fournir un
    tuple ``("col" "other_col")`` où ``col`` est le nom utilisé dans
    ``func`` et ``other_col`` est la vraie colonne utilisée.

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
        Un message décrivant l'opération

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

    - Recalcul avec une note modifiée sans redéfinir la function ``moyenne`` :

      .. code:: python

         from guv.helpers import compute_new_column

         DOCS.compute_new_column(
             ("note1", "note1_fix"), "note2", "note3", func=moyenne, colname="Note_moyenne (fix)"
         )

    """

    def __init__(self, *cols: str, func: Callable, colname: str, msg: Optional[str] = None):
        super().__init__()
        self.col2id = {}
        for col in cols:
            if isinstance(col, tuple):
                self.col2id[col[1]] = col[0]
            else:
                self.col2id[col] = col
        self.func = func
        self.colname = colname
        self.msg = msg

    def apply(self, df):
        check_if_present(df, self.col2id.keys())
        check_if_absent(df, self.colname, errors="warning")

        def compute_value(row):
            # Extract values from row and rename
            values = row.loc[list(self.col2id.keys())]
            values = values.rename(index=self.col2id)

            return self.func(values)

        new_col = df.apply(compute_value, axis=1)
        df = df.assign(**{self.colname: new_col})
        return df

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg

        return f"Calcul de la colonne `{self.colname}`"


class ApplyCell(Operation):
    """Remplace la valeur d'une cellule.

    ``name_or_email`` est le nom-prénom de l'étudiant ou son adresse
    courriel et ``colname`` est le nom de la colonne où faire le
    changement. La nouvelle valeur est renseignée par ``value``.

    Parameters
    ----------

    name_or_email : :obj:`str`
        Le nom-prénom ou l'adresse courriel de l'étudiant.

    colname : :obj:`str`
        Le nom de la colonne où faire les modifications.

    value :
        La valeur à affecter.

    msg : :obj:`str`
        Un message décrivant l'opération

    Examples
    --------

    .. code:: python

       DOCS.apply_cell("Mark Watney", "Note bricolage", 20)

    """

    def __init__(self, name_or_email: str, colname: str, value, msg: Optional[str] = None):
        super().__init__()
        self.name_or_email = name_or_email
        self.colname = colname
        self.value = value
        self.msg = msg

    def apply(self, df):
        check_if_present(df, self.colname)

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
        check_if_absent(df, "fullname_slug")
        df["fullname_slug"] = tf_df(df)

        if '@etu' in self.name_or_email:
            sturow = df.loc[df['Courriel'] == self.name_or_email]
            if len(sturow) > 1:
                raise Exception(f'Adresse courriel `{self.name_or_email}` présente plusieurs fois')
            if len(sturow) == 0:
                raise Exception(f'Adresse courriel `{self.name_or_email}` non présente dans le fichier central')
            stuidx = sturow.index[0]
        else:
            sturow = df.loc[df.fullname_slug == slugrot_string(self.name_or_email)]
            if len(sturow) > 1:
                raise Exception(f'Étudiant de nom `{self.name_or_email}` présent plusieurs fois')
            if len(sturow) == 0:
                raise Exception(f'Étudiant de nom `{self.name_or_email}` non présent dans le fichier central')
            stuidx = sturow.index[0]

        df.loc[stuidx, self.colname] = self.value

        df = df.drop('fullname_slug', axis=1)
        return df

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg

        return f"Modification de la colonne `{self.colname}` pour l'identifiant `{self.name_or_email}`"


class FileOperation(Operation):
    def __init__(self, filename, base_dir=None):
        super().__init__()
        self._filename = filename
        self.base_dir = base_dir

    @property
    def filename(self):
        if self.base_dir:
            return os.path.join(self.base_dir, self._filename)

        return self._filename

    @property
    def deps(self):
        return [self.filename]

    def message(self, ref_dir=""):
        return f"Agrégation du fichier `{rel_to_dir(self.filename, ref_dir)}`"


class Add(FileOperation):
    """Déclare une agrégation d'un fichier à l'aide d'une fonction.

    Fonction générale pour déclarer l'agrégation d'un fichier de
    chemin ``filename`` à l'aide d'une fonction ``func`` prenant
    en argument le *DataFrame* déjà existant, le chemin vers le
    fichier et renvoie le *DataFrame* mis à jour.

    Voir fonctions spécialisées pour l'incorporation de documents
    classiques :

    - :func:`~guv.helpers.Documents.aggregate` : Document csv/Excel
    - :func:`~guv.helpers.Documents.aggregate_org` : Document Org

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier à agréger.

    func : :obj:`callable`
        Une fonction de signature *DataFrame*, filename: str ->
        *DataFrame* qui réalise l'agrégation.

    Examples
    --------

    .. code:: python

       def fonction_qui_incorpore(df, file_path):
           # On incorpore le fichier dont le chemin est `file_path` au
           # DataFrame `df` et on renvoie le DataFrame mis à jour.

       DOCS.add("documents/notes.csv", func=fonction_qui_incorpore)

    """

    def __init__(self, filename, func):
        super().__init__(filename)
        self.func = func

    def apply(self, df):
        return self.func(df, self.filename)


class Aggregate(FileOperation):
    """Agrégation d'un tableau provenant d'un fichier Excel/csv.

    Les arguments ``left_on`` et ``right_on`` sont des noms de colonnes pour
    réaliser une jointure : ``left_on`` est une colonne présente dans le fichier
    central ``effectif.xlsx`` et ``right_on`` est une colonne du fichier à
    agréger. Dans le cas où la jointure est plus complexe, on peut utiliser les
    fonctions :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` (voir
    Exemples) Dans le cas où ``left_on`` et ``right_on`` ont la même valeur, on
    peut seulement spécifier ``on``.

    ``subset`` est une liste des colonnes à garder si on ne veut pas agréger la
    totalité des colonnes, ``drop`` une liste des colonnes à enlever. ``rename``
    est un dictionnaire des colonnes à renommer. ``read_method`` est un
    *callable* appelé avec ``kw_read`` pour lire le fichier contenant le
    *DataFrame* à agréger. ``preprocessing`` et ``postprocessing`` sont des
    *callable* qui prennent en argument un *DataFrame* et en renvoie un et qui
    réalise respectivement un pré-traitement sur le fichier à agréger ou un
    post-traitement sur l'agrégation.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier csv/Excel à agréger.

    left_on : :obj:`str`
        Le nom de colonne présent dans le fichier ``effectif.xlsx`` pour
        réaliser la jointure. On peut également utiliser les fonctions
        :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` pour une
        jointure prenant en compte plusieurs colonnes.

    right_on : :obj:`str`
        Le nom de colonne présent dans le fichier à incorporer pour
        réaliser la jointure. On peut également utiliser les fonctions
        :func:`guv.helpers.id_slug` et :func:`guv.helpers.concat` pour une
        jointure prenant en compte plusieurs colonnes.

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
           kw_read={"na_values": "-"}

    preprocessing : :obj:`callable`, optional
        Pré-traitement à appliquer au *DataFrame* avant de l'intégrer.

    postprocessing : :obj:`callable`, optional
        Post-traitement à appliquer au *DataFrame* après intégration du fichier.

    Examples
    --------

    - Agrégation des colonnes d'un fichier csv suivant la colonne
      ``email`` du fichier csv et ``Courriel`` du fichier central :

      .. code:: python

         DOCS.aggregate(
             "documents/notes.csv",
             left_on="Courriel",
             right_on="email"
         )

    - Agrégation de la colonne ``Note`` d'un fichier csv suivant la
      colonne ``email`` du fichier csv et ``Courriel`` du fichier
      central :

      .. code:: python

         DOCS.aggregate(
             "documents/notes.csv",
             left_on="Courriel",
             right_on="email",
             subset="Note"
         )

    - Agrégation de la colonne ``Note`` renommée en ``Note_médian``
      d'un fichier csv suivant la colonne ``email`` du fichier csv et
      ``Courriel`` du fichier central :

      .. code:: python

         DOCS.aggregate(
             "documents/notes.csv",
             left_on="Courriel",
             right_on="email",
             subset="Note",
             rename={"Note": "Note_médian"}
         )

    - Agrégation de la colonne ``Note`` suivant ``Courriel`` en
      spécifiant l'en-tête absente du fichier csv :

      .. code:: python

         DOCS.aggregate(
             "documents/notes.csv",
             on="Courriel",
             kw_read={"header": None, "names": ["Courriel", "Note"]},
         )

    - Agrégation d'un fichier csv de notes suivant les colonnes ``Nom`` et
      ``Prénom`` en calculant un identifiant (slug) sur ces deux colonnes pour
      une mise en correspondance plus souple (robuste par rapport aux accents,
      majuscules, tirets,...) :

      .. code:: python

         from guv.helpers import slugrot
         DOCS.aggregate(
             "documents/notes.csv",
             left_on=id_slug("Nom", "Prénom"),
             right_on=id_slug("Nom", "Prénom")
         )

    - Agrégation d'un fichier csv de notes suivant les colonnes ``Nom`` et
      ``Prénom`` en les concaténant car le fichier à agréger contient seulement
      une colonne avec ``Nom`` et ``Prénom`` :

      .. code:: python

         from guv.helpers import slugrot
         DOCS.aggregate(
             "documents/notes.csv",
             left_on=concat("Nom", "Prénom"),
             right_on="Nom_Prénom"
         )

    """

    def __init__(
        self,
        filename: str,
        *,
        left_on: Union[None, str, callable] = None,
        right_on: Union[None, str, callable] = None,
        on: Optional[str] = None,
        subset: Union[None, str, List[str]] = None,
        drop: Union[None, str, List[str]] = None,
        rename: Optional[dict] = None,
        preprocessing: Union[None, Callable, Operation] = None,
        postprocessing: Union[None, Callable, Operation] = None,
        read_method: Optional[Callable] = None,
        kw_read: Optional[dict] = {}
    ):
        super().__init__(filename)
        self._filename = filename
        self.left_on = left_on
        self.right_on = right_on
        self.on = on
        self.subset = subset
        self.drop = drop
        self.rename = rename
        self.preprocessing = preprocessing
        self.postprocessing = postprocessing
        self.read_method = read_method
        self.kw_read = kw_read

    def apply(self, left_df):
        # Infer a read method if not provided
        if self.read_method is None:
            if self.filename.endswith('.csv'):
                right_df = pd.read_csv(self.filename, **self.kw_read)
            elif self.filename.endswith('.xlsx') or self.filename.endswith('.xls'):
                right_df = pd.read_excel(self.filename, engine="openpyxl", **self.kw_read)
            else:
                raise Exception('No read method and unsupported file extension')
        else:
            right_df = self.read_method(self.filename, **self.kw_read)

        if self.on is not None:
            if self.left_on is not None or self.right_on is not None:
                raise ImproperlyConfigured("On doit spécifier soit `on`, soit `left_on` et `right_on`.")

            left_on = self.on
            right_on = copy.copy(self.on) # Duplicate because left_on and right_on must be different
        else:
            left_on = self.left_on
            right_on = self.right_on

        agg = Aggregator(
            left_df,
            right_df,
            left_on=left_on,
            right_on=right_on,
            preprocessing=self.preprocessing,
            postprocessing=self.postprocessing,
            subset=self.subset,
            drop=self.drop,
            rename=self.rename,
        )

        return agg.left_aggregate()


class AggregateSelf(Operation):
    """Agrégation du fichier central ``effectif.xlsx`` lui-même.

    Il est parfois plus pratique d'ajouter soi-même des colonnes dans le fichier
    central ``effectif.xlsx`` au lieu d'en ajouter programmatiquement via
    ``DOCS.aggregate(...)`` par exemple. Comme *guv* ne peut pas détecter de
    façon fiable les colonnes ajoutées, il faut lui indiquer lesquelles ont été
    manuellement ajoutées et qu'il faut garder lors de la mise à jour du fichier
    central ``effectif.xlsx``.

    Parameters
    ----------

    *columns : any number of :obj:`str`
        Les colonnes manuellement ajoutées à garder lors de la mise à jour du fichier central.

    """

    def __init__(self, *columns):
        super().__init__()
        self.columns = columns

    def apply(self, left_df):
        from .tasks.students import XlsStudentDataMerge # Circular deps
        right_df = XlsStudentDataMerge.read_target(XlsStudentDataMerge.target_from(**self.info))

        agg = Aggregator(
            left_df,
            right_df,
            left_on="Login",
            right_on="Login",
            subset=list(self.columns),
        )

        agg_df = agg.left_aggregate()
        return agg.merge_columns(agg_df, strategy="keep_right", columns=self.columns)

    def message(self, ref_dir=None):
        msg = ", ".join(f"`{e}`" for e in self.columns)
        return f"Ajoute les colonnes manuelles : {msg}"


class AggregateOrg(FileOperation):
    """Agrégation d'un fichier au format Org.

    Le document à agréger est au format Org. Les titres servent de clé
    pour l'agrégation et le contenu de ces titres est agrégé.

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
        Post-traitement à appliquer au *DataFrame* après intégration
        du fichier Org.

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

    def __init__(
        self,
        filename: str,
        colname: str,
        on: Optional[str] = None,
        postprocessing: Union[None, Callable, Operation] = None,
    ):
        super().__init__(filename)
        self._filename = filename
        self.colname = colname
        self.on = on
        self.postprocessing = postprocessing

    def apply(self, left_df):
        check_filename(self.filename, base_dir=settings.SEMESTER_DIR)

        def parse_org(text):
            for chunk in re.split("^\\* *", text, flags=re.MULTILINE)[1:]:
                if not chunk:
                    continue
                header, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                logger.debug("Header line: %s", header)
                yield header, text

        text = open(self.filename, 'r').read()
        df_org = pd.DataFrame(parse_org(text), columns=["header", self.colname])

        if self.on is None:
            left_on = id_slug("Nom", "Prénom")
            right_on = id_slug("header")
        else:
            left_on = self.on
            right_on = "header"

        agg = Aggregator(left_df, df_org, left_on, right_on, postprocessing=self.postprocessing)
        return agg.left_aggregate()


class AggregateAmenagements(FileOperation):
    """Agrégation du fichier des aménagements pour les examens.

    Le document à agréger est disponible
    [ici](https://webapplis.utc.fr/amenagement/examens/enseignant/suivi-demandes.xhtml).

    Il s'agit d'un fichier Excel dont le format est trop vieux pour être chargé
    directement. Il faut au préalable l'enregistrer au format xlsx.

    Parameters
    ----------

    filename : :obj:`str`
        Le chemin du fichier Excel d'aménagements à agréger.

    Examples
    --------

    .. code:: python

       DOCS.aggregate_amenagements("documents/amenagements_examens_Printemps_2024_SY02.xlsx")

    """

    def __init__(self, filename: str):
        super().__init__(filename)
        self._filename = filename

    def apply(self, left_df):
        check_filename(self.filename, base_dir=settings.SEMESTER_DIR)

        try:
            right_df = pd.read_excel(self.filename, engine="openpyxl")
        except zipfile.BadZipFile:
            fn = rel_to_dir(self.filename, settings.CWD)
            raise Exception(f"Le fichier `{fn}` n'est pas reconnu. Merci de le réenregistrer avec Excel au format xlsx.")

        def is_tt(row):
            s = str(row["Aménagements"])
            if "Temps de composition majoré d'un tiers" in s and "pour les épreuves écrites" in s:
                return "Oui"
            else:
                return "Non"

        def is_dys(row):
            s = str(row["Aménagements"])
            if "Adaptation dans la présentation des sujets" in s:
                return "Oui"
            else:
                return "Non"

        agg = Aggregator(
            left_df,
            right_df,
            id_slug("Nom", "Prénom"),
            id_slug("Etudiant"),
            subset="Aménagements",
            postprocessing=[
                compute_new_column("Aménagements", func=is_tt, colname="Salle dédiée"),
                compute_new_column("Aménagements", func=is_dys, colname="Sujet spécifique")
            ],
        )

        return agg.left_aggregate()


class FileStringOperation(FileOperation):
    msg_file = "Agrégation du fichier `{filename}`"
    msg_string = "Agrégation directe de \"{string}\""

    def __init__(self, filename_or_string, base_dir=None):
        super().__init__(filename_or_string)
        self.filename_or_string = filename_or_string
        self.base_dir = base_dir
        self._is_file = None

    @property
    def is_file(self):
        if self._is_file is None:
            # Heuristic to decide whether `filename_or_string` is a file or
            # string
            self._is_file = (
                "\n" not in self.filename_or_string
                and "---" not in self.filename_or_string
                and "*" not in self.filename_or_string
            )

        return self._is_file

    @property
    def lines(self):
        if self.is_file:
            if self.base_dir:
                filename =  os.path.join(self.base_dir, self.filename_or_string)
            else:
                filename = self.filename_or_string

            check_filename(filename, base_dir=self.base_dir)
            lines = open(filename, "r").readlines()
        else:
            lines = self.filename_or_string.splitlines(keepends=True)

        return lines

    @property
    def deps(self):
        if self.is_file:
            return [self.filename_or_string]
        else:
            return []

    def message(self, ref_dir=""):
        if self.is_file:
            return self.msg_file.format(filename=rel_to_dir(self.filename_or_string, ref_dir))
        else:
            return self.msg_string.format(string=self.filename_or_string.lstrip().splitlines()[0] + "...")


class Flag(FileStringOperation):
    """Signaler une liste d'étudiants dans une nouvelle colonne.

    Le document à agréger est une liste de noms d'étudiants affichés
    ligne par ligne.

    Parameters
    ----------

    filename_or_string : :obj:`str`
        Le chemin du fichier à agréger ou directement le texte du fichier.

    colname : :obj:`str`
        Nom de la colonne dans laquelle mettre le drapeau.

    flags : :obj:`str`, optional
        Les deux drapeaux utilisés, par défaut "Oui" et vide.

    Examples
    --------

    Agrégation d'un fichier avec les noms des étudiants pour titre :

    Le fichier "tiers_temps.txt" :

    .. code:: text

       # Des commentaires
       Bob Morane

       # Robuste à la permutation circulaire et à la casse
       aRcTor BoB

    L'instruction d'agrégation :

    .. code:: python

       DOCS.flag("documents/tiers_temps.txt", colname="Tiers-temps")

    """

    def __init__(self, filename_or_string: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
        super().__init__(filename_or_string)
        self.colname = colname
        self.flags = flags

    def apply(self, df):
        check_if_absent(df, self.colname)

        df[self.colname] = self.flags[1]

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        for line in self.lines:
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
            if len(res) > 1:
                raise Exception('Plusieurs correspondances pour `{:s}`'.format(line))
            df.loc[res.index[0], self.colname] = self.flags[0]

        df = df.drop('fullname_slug', axis=1)
        return df


class Switch(FileStringOperation):
    """Réalise des échanges de valeurs dans une colonne.

    L'argument ``colname`` est la colonne dans laquelle opérer les
    échanges. Si l'argument ``backup`` est spécifié, la colonne est
    sauvegardée avant toute modification (avec un suffixe ``_orig``).
    Si l'argument ``new_colname`` est fourni la colonne est copiée
    vers une nouvelle colonne de nom ``new_colname`` et les
    modifications sont faites sur cette nouvelle colonne.

    Parameters
    ----------

    filename_or_string : :obj:`str`
        Le chemin du fichier à agréger ou directement le texte du fichier.
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

    .. code:: python

       DOCS.switch("Dupont --- Dupond", colname="TP")

    """

    msg_file = "Agrégation du fichier d'échanges `{filename}`"
    msg_string = "Agrégation directe des échanges \"{string}\""

    def __init__(
        self,
        filename_or_string: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: Optional[str] = None,
    ):
        super().__init__(filename_or_string)
        self.colname = colname
        self.backup = backup
        self.new_colname = new_colname

    def apply(self, df):

        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                "Les arguments `backup` et `new_colname` sont incompatibles."
            )

        # Check that column exist
        check_if_present(df, self.colname)

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        new_column = swap_column(df, self.lines, self.colname)
        df = replace_column_aux(
            df,
            colname=self.colname,
            new_colname=self.new_colname,
            new_column=new_column,
            backup=self.backup,
            errors="silent"
        )

        df = df.drop("fullname_slug", axis=1)
        return df


def replace_column_aux(
        df, new_colname=None, colname=None, new_column=None, backup=False, errors="warning"
):
    """Helper function for `replace_regex` and `replace_column`."""

    if backup:
        check_if_absent(df, f"{colname}_orig", errors="warning")
        df = df.assign(**{f"{colname}_orig": df[colname]})
        target_colname = colname
    elif new_colname is not None:
        target_colname = new_colname
    else:
        target_colname = colname

    check_if_absent(df, target_colname, errors=errors)
    df = df.assign(**{target_colname: new_column})

    return df


def read_pairs(lines):
    """Generate pairs read in `lines`. """

    for line in lines:
        if line.strip().startswith("#"):
            continue
        if not line.strip():
            continue
        try:
            parts = [e.strip() for e in line.split("---")]
            stu1, stu2 = parts
            if not stu1 or not stu2:
                raise Exception(f"Ligne incorrecte: `{line.strip()}`. Format `etu1 --- etu2` attendu.")
            yield stu1, stu2
        except ValueError:
            raise Exception(f"Ligne incorrecte: `{line.strip()}`. Format `etu1 --- etu2` attendu.")


def validate_pair(df, colname, part1, part2):
    """Return action to do with a pair `part1`, `part2`."""

    names = df[colname].unique()

    # Indice de l'étudiant 1
    if "@etu" in part1:
        stu1row = df.loc[df["Courriel"] == part1]
        if len(stu1row) != 1:
            raise Exception(
                f"Adresse courriel `{part1}` non présente dans le fichier central"
            )
        stu1idx = stu1row.index[0]
    else:
        stu1row = df.loc[df.fullname_slug == slugrot_string(part1)]
        if len(stu1row) != 1:
            raise Exception(
                f"Étudiant de nom `{part1}` non présent ou reconnu dans le fichier central"
            )
        stu1idx = stu1row.index[0]

    if part2 in names:  # Le deuxième élément est une colonne
        return "move", stu1idx, part2
    elif part2 in ["null", "nan"]:
        return "quit", stu1idx, None
    elif "@etu" in part2:  # Le deuxième élément est une adresse email
        stu2row = df.loc[df["Courriel"] == part2]
        if len(stu2row) != 1:
            raise Exception(
                f"Adresse courriel `{part2}` non présente dans le fichier central"
            )
        stu2idx = stu2row.index[0]
        return "swap", stu1idx, stu2idx
    else:
        stu2row = df.loc[df.fullname_slug == slugrot_string(part2)]
        if len(stu2row) != 1:
            raise Exception(
                f"Étudiant ou nom de séance `{part2}` non reconnu dans le fichier central"
            )
        stu2idx = stu2row.index[0]
        return "swap", stu1idx, stu2idx


def swap_column(df, lines, colname):
    """Return copy of column `colname` modified by swaps from `lines`. """

    new_column = df[colname].copy()

    for part1, part2 in read_pairs(lines):
        type, idx1, idx2 = validate_pair(df, colname, part1, part2)

        if type == "swap":
            nom1 = " ".join(df.loc[idx1, ["Nom", "Prénom"]])
            nom2 = " ".join(df.loc[idx2, ["Nom", "Prénom"]])
            logger.info("Échange de `%s` et `%s` dans la colonne `%s`", nom1, nom2, colname)

            tmp = new_column[idx1]
            new_column[idx1] = new_column[idx2]
            new_column[idx2] = tmp
        elif type == "move":
            nom = " ".join(df.loc[idx1, ["Nom", "Prénom"]])
            logger.info("Étudiant(e) `%s` affecté(e) au groupe `%s`", nom, idx2)

            new_column[idx1] = idx2
        elif type == "quit":
            nom = " ".join(df.loc[idx1, ["Nom", "Prénom"]])
            logger.info("Abandon étudiant(e) `%s`", nom)

            new_column[idx1] = np.nan

    return new_column


class AggregateMoodleGroups(FileOperation):
    """Agrège des données de groupes issue de l'activité "Choix de Groupe".

    Le nom de la colonne des groupes étant toujours "Groupe", l'argument
    ``colname`` permet d'en spécifier un nouveau.

    Examples
    --------

    .. code:: python

       DOCS.aggregate_moodle_groups("documents/Paper study groups.xlsx", "Paper")

    """

    def __init__(self, filename: str, colname: str):
        super().__init__(filename)
        self.colname = colname

    def apply(self, df):
        if re.match(r"^\w+@", df.iloc[0]["Courriel"]) is not None:
            left_on = id_slug("Nom", "Prénom")
            right_on = id_slug("Nom", "Prénom")
            drop=["Nom", "Prénom", "Numéro d'identification", "Choix", "Adresse de courriel"]
        else:
            left_on = "Courriel"
            right_on = "Adresse de courriel"
            drop=["Nom", "Prénom", "Numéro d'identification", "Choix"]

        op = Aggregate(
            self.filename,
            left_on=left_on,
            right_on=right_on,
            drop=drop,
            rename={"Groupe": self.colname}
        )
        return op.apply(df)


class AggregateMoodleGrades(FileOperation):
    """Agrège des feuilles de notes provenant de Moodle.

    La feuille de notes peut être un export du carnet de notes de Moodle, un
    export des notes d'une activité quiz ou un export d'une activité devoir sous
    la forme d'un fichier Excel ou csv.

    Les colonnes inutiles seront éliminées. Un renommage des colonnes peut être
    effectué en renseignant ``rename``.

    Examples
    --------

    .. code:: python

       DOCS.aggregate_moodle_grades("documents/SY02 Notes.xlsx")

    """

    gradesheet_columns = [
        "Prénom",
        "Nom",
        "Numéro d'identification",
        "Institution",
        "Département",
        "Adresse de courriel",
        "Dernier téléchargement depuis ce cours",
    ]

    quiz_columns = [
        "Nom",
        "Prénom",
        "Adresse de courriel",
        "État",
        "Commencé le",
        "Terminé",
        "Temps utilisé",
    ]

    assignment_columns = [
        "Identifiant",
        "Nom complet",
        "Adresse de courriel",
        "Statut",
        "Groupe",
        "Note maximale",
        "La note peut être modifiée",
        "Dernière modification (travail remis)",
        "Dernière modification (note)",
        "Feedback par commentaires",
    ]

    def __init__(
        self,
        filename: str,
        rename: Optional[dict] = None,
    ):
        super().__init__(filename)
        self.rename = rename

    def load_filename(self):
        kw_read = {"na_values": "-"}
        if self.filename.endswith(".csv"):
            right_df = pd.read_csv(self.filename, **kw_read)
        elif self.filename.endswith(".xlsx") or self.filename.endswith(".xls"):
            right_df = pd.read_excel(self.filename, engine="openpyxl", **kw_read)
        else:
            raise Exception("Fichier Excel ou csv seulement")

        return right_df

    def apply(self, left_df):
        right_df = self.load_filename()
        columns = set(right_df.columns.values)

        is_gradesheet = set(self.gradesheet_columns).issubset(set(columns))
        is_quiz = set(self.quiz_columns).issubset(set(columns))
        is_assignment = set(self.assignment_columns).issubset(set(columns))

        if is_gradesheet:
            drop = self.gradesheet_columns
            logger.debug("Feuille de notes reconnue")
        elif is_quiz:
            drop = self.quiz_columns
            logger.debug("Feuille de notes de quiz reconnue")
        elif is_assignment:
            drop = self.assignment_columns
            logger.debug("Feuille de notes de devoir reconnue")
        else:
            raise Exception("Le fichier n'est pas reconnu comme une feuille de notes Moodle")

        moodle_short_email = (
            re.match(f"^\w+@", right_df.iloc[0]["Adresse de courriel"]) is not None
        )
        ent_short_email = re.match(f"^\w+@", left_df.iloc[0]["Courriel"]) is not None

        def left_right():
            if not (moodle_short_email ^ ent_short_email):
                return "Courriel", "Adresse de courriel"

            if "Adresse de courriel" in left_df.columns:
                ent_short_email2 = (
                    re.match(f"^\w+@", left_df.iloc[0]["Adresse de courriel"])
                    is not None
                )
                if not (moodle_short_email ^ ent_short_email2):
                    return "Adresse de courriel", "Adresse de courriel"

            if is_assignment:
                right_on = id_slug("Nom complet")
            else:
                right_on = id_slug("Nom", "Prénom")

            if "Nom_moodle" in left_df.columns and "Prénom_moodle" in left_df.columns:
                left_on = id_slug("Nom_moodle", "Prénom_moodle")
            else:
                left_on = id_slug("Nom", "Prénom")

            return left_on, right_on

        left_on, right_on = left_right()

        # Don't try to drop a required column
        if right_on in drop:
            drop.remove(right_on)

        agg = Aggregator(
            left_df=left_df,
            right_df=right_df,
            left_on=left_on,
            right_on=right_on,
            rename=self.rename,
            drop=drop,
        )
        return agg.left_aggregate()


class AggregateJury(FileOperation):
    """Agrège le résultat d'un jury provenant de la tâche
    :class:`~guv.tasks.gradebook.XlsGradeBookJury`.

    L'équivalent avec :func:`~guv.helpers.Documents.aggregate` s'écrit :

    .. code:: python

       DOCS.aggregate(
           "generated/Jury_gradebook.xlsx",
           on="Courriel",
           subset=["Note agrégée", "Note ECTS"]
       )

    Examples
    --------

    .. code:: python

       DOCS.aggregate_jury("generated/Jury_gradebook.xlsx")

    """

    def __init__(self, filename: str):
        super().__init__(filename)

    def apply(self, df):
        op = Aggregate(
            self.filename,
            on="Courriel",
            subset=["Note agrégée", "Note ECTS"]
        )
        return op.apply(df)


class Documents:
    def __init__(self, base_dir=None, info=None):
        self.info = info
        self._base_dir = base_dir
        self._actions = []

    @property
    def base_dir(self):
        return self._base_dir

    @base_dir.setter
    def base_dir(self, value):
        self._base_dir = value
        for a in self.actions:
            a.base_dir = value

    def add_action(self, action):
        action.base_dir = self.base_dir
        action.info = self.info
        self._actions.append(action)

    @property
    def actions(self):
        return self._actions

    @property
    def deps(self):
        return [d for a in self.actions for d in a.deps]

    def apply_actions(self, df, ref_dir=""):
        for action in self.actions:
            logger.info(action.message(ref_dir=ref_dir))
            df = action.apply(df)
        return df


def add_action_method(cls, klass, method_name):
    """Add new method named `method_name` to class `cls`"""

    @functools.wraps(klass.__init__)
    def dummy(self, *args, **kwargs):
        action = klass(*args, **kwargs)
        self.add_action(action)

    dummy.__doc__ = klass.__doc__
    dummy.__name__ = method_name

    setattr(cls, method_name, dummy)


actions = [
    ("fillna_column", FillnaColumn),
    ("replace_regex", ReplaceRegex),
    ("replace_column", ReplaceColumn),
    ("apply_df", ApplyDf),
    ("apply_column", ApplyColumn),
    ("compute_new_column", ComputeNewColumn),
    ("add", Add),
    ("aggregate", Aggregate),
    ("aggregate_self", AggregateSelf),
    ("aggregate_moodle_grades", AggregateMoodleGrades),
    ("aggregate_moodle_groups", AggregateMoodleGroups),
    ("aggregate_jury", AggregateJury),
    ("aggregate_org", AggregateOrg),
    ("aggregate_amenagements", AggregateAmenagements),
    ("flag", Flag),
    ("apply_cell", ApplyCell),
    ("switch", Switch),
]

for method_name, klass in actions:
    # Add as method
    add_action_method(Documents, klass, method_name)

    # Add as a standalone fonction
    def make_func(klass):
        def dummy(*args, **kwargs):
            return klass(*args, **kwargs)
        dummy.__doc__ = klass.__doc__
        return dummy

    globals()[method_name] = make_func(klass)

def skip_range(d1, d2):
    return [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]


def skip_week(d1, weeks=1):
    return [d1 + timedelta(days=x) for x in range(7*weeks-1)]
