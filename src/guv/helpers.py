import os
import functools
import re
import textwrap
from collections.abc import Callable
from datetime import timedelta
from typing import List, Optional, Union

import pandas as pd

from .config import logger
from .exceptions import ImproperlyConfigured
from .utils import check_filename, slugrot_string
from .utils_config import rel_to_dir, check_columns


def slugrot(*columns):
    "Rotation-invariant hash function on a dataframe"

    def func(df):
        check_columns(df, columns)
        s = df[list(columns)].apply(
            lambda x: "".join(x.astype(str)),
            axis=1
        )

        s = s.apply(slugrot_string)
        s.name = "_".join(columns)
        return s

    return func


class Operation:
    """Base class for operation to apply to `effectif.xlsx`."""

    def message(self, **kwargs):
        return "Pas de message"

    @property
    def deps(self):
        return []

    def apply(self, df):
        pass


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
            check_columns(df, [self.colname])
            df[self.colname].fillna(self.na_value, inplace=True)
        else:
            def fill_by_group(g):
                idx_first = g[self.colname].first_valid_index()
                idx_last = g[self.colname].last_valid_index()
                if idx_first is not None:
                    if idx_first == idx_last:
                        g[self.colname] = g.loc[idx_first, self.colname]
                    else:
                        logger.warning("Plusieurs valeurs non-NA dans le groupe `%s`", g)
                else:
                    logger.warning("Aucune valeur non-NA dans le groupe `%s`", g)
                return g

            check_columns(df, [self.colname, self.group_column])
            df = df.groupby(self.group_column).apply(fill_by_group)

        return df

    def message(self, **kwargs):
        if self.na_value is not None:
            return f"Remplace les NA dans la colonne `{self.colname}` par la valeur `{self.na_value}`"
        else:
            return f"Remplace les NA dans la colonne `{self.colname}` en groupant par `{self.group_column}`"


class ReplaceRegex(Operation):
    """Remplacements regex dans une colonne.

    Remplace dans la colonne ``colname`` les occurrences de toutes les
    expressions régulières renseignées dans ``reps``.

    Si l'argument ``backup`` est spécifié, la colonne est sauvegardée
    avant toute modification (avec un suffixe ``_orig``). Si
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

        check_columns(df, self.colname)

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

        check_columns(df, self.colname)
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
        elif self.new_colname is None:
            return f"Remplacement dans colonne `{self.colname}`"
        else:
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
        Un message descriptif utilisé

    Examples
    --------

    .. code:: python

       DOCS.apply_df(
           lambda df: df.loc[~df["Adresse de courriel"].duplicated(), :],
           msg="Retirer les utilisateurs dupliqués"
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
        else:
            return "Appliquer une fonction au Dataframe"


class ApplyColumn(Operation):
    """Modifie une colonne existente avec une fonction.

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

    def __init__(self, colname: str, func: Callable, msg: Optional[str] = None):
        super().__init__()
        self.colname = colname
        self.func = func
        self.msg = msg

    def apply(self, df):
        check_columns(df, self.colname)
        df.loc[:, self.colname] = df[self.colname].apply(self.func)
        return df

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg
        else:
            return f"Appliquer une fonction à la colonne `{self.colname}`"


class ComputeNewColumn(Operation):
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

    def __init__(self, *cols: str, func: Callable, colname: str, msg: Optional[str] = None):
        super().__init__()
        self.cols = cols
        self.func = func
        self.colname = colname
        self.msg = msg

    def apply(self, df):
        check_columns(df, self.cols)
        new_col = df.apply(lambda x: self.func(x.loc[list(self.cols)]), axis=1)
        df = df.assign(**{self.colname: new_col})
        return df

    def message(self, **kwargs):
        if self.msg is not None:
            return self.msg
        else:
            return f"Calcul de la colonne `{self.colname}`"


class ApplyCell(Operation):
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

    def __init__(self, name_or_email: str, colname: str, value):
        super().__init__()
        self.name_or_email = name_or_email
        self.colname = colname
        self.value = value

    def apply(self, df):
        check_columns(df, columns=self.colname, error_when="not_found")

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
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
        else:
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

    Les arguments ``left_on`` et ``right_on`` sont les clés pour
    réaliser une jointure : ``left_on`` est la clé du *DataFrame*
    existant et ``right_on`` est la clé du *DataFrame* à agréger présent
    dans le fichier. ``left_on`` et ``right_on`` peuvent aussi être
    des callable prenant en argument le *DataFrame* correspondant et
    renvoyant une nouvelle colonne avec laquelle faire la jointure.
    Dans le cas où ``left_on`` et ``right_on`` ont la même valeur, on
    peut seulement spécifier ``on``.

    ``subset`` est une liste des colonnes à garder si on ne veut pas
    agréger la totalité des colonnes, ``drop`` une liste des colonnes
    à enlever. ``rename`` est un dictionnaire des colonnes à renommer.
    ``read_method`` est un *callable* appelé avec ``kw_read`` pour lire
    le fichier contenant le *DataFrame* à agréger. ``preprocessing`` et
    ``postprocessing`` sont des *callable* qui prennent en argument un
    *DataFrame* et en renvoie un et qui réalise un pré ou post
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
        jointure (voir fonction :func:`guv.helpers.slugrot`).

    right_on : :obj:`str`
        Le nom de colonne présent dans le fichier à incorporer pour
        réaliser la jointure. Au cas où la colonne n'existe pas,
        on peut spécifier une fonction prenant en argument le
        *DataFrame* et renvoyant une *Series* utilisée pour la
        jointure (voir fonction :func:`guv.helpers.slugrot`).

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

    - Agrégation d'un fichier csv de notes suivant les colonnes
      ``Nom`` et ``Prénom`` en calculant un *slug* sur ces deux
      colonnes pour une mise en correspondance plus souple (accents,
      majuscules, tirets,...) :

      .. code:: python

         from guv.helpers import slugrot
         DOCS.aggregate(
             "documents/notes.csv",
             left_on=slugrot("Nom", "Prénom"),
             right_on=slugrot("Nom", "Prénom")
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

            left_on = right_on = self.on
        else:
            left_on = self.left_on
            right_on = self.right_on

        return aggregate_df(
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


class AggregateOrg(FileOperation):
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

    def __init__(self,
        filename: str,
        colname: str,
        on: Optional[str] = None,
        postprocessing: Union[None, Callable, Operation] = None
    ):
        super().__init__(filename)
        self._filename = filename
        self.colname = colname
        self.on = on
        self.postprocessing = postprocessing

    def apply(self, left_df):
        check_filename(self.filename)

        def parse_org(text):
            for chunk in re.split("^\\* *", text, flags=re.MULTILINE):
                if not chunk:
                    continue
                header, *text = chunk.split("\n", maxsplit=1)
                text = "\n".join(text).strip("\n")
                text = textwrap.dedent(text)
                yield header, text

        text = open(self.filename, 'r').read()
        df_org = pd.DataFrame(parse_org(text), columns=["header", self.colname])

        if self.on is None:
            left_on = slugrot("Nom", "Prénom")
            right_on = slugrot("header")
        else:
            left_on = self.on
            right_on = "header"

        df = aggregate_df(left_df, df_org, left_on, right_on, postprocessing=self.postprocessing)
        return df


class Flag(FileOperation):
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

    def __init__(self, filename: str, *, colname: str, flags: Optional[List[str]] = ["Oui", ""]):
        super().__init__(filename)
        self.colname = colname
        self.flags = flags

    def apply(self, df):
        check_filename(self.filename)
        check_columns(df, self.colname, error_when="exists")

        df[self.colname] = self.flags[1]

        # Add column that acts as a primary key
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        with open(self.filename, 'r') as fd:
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
                df.loc[res.index[0], self.colname] = self.flags[0]

        df = df.drop('fullname_slug', axis=1)
        return df


class Switch(FileOperation):
    """Réalise des échanges de valeurs dans une colonne.

    L'argument ``colname`` est la colonne dans laquelle opérer les
    échanges. Si l'argument ``backup`` est spécifié, la colonne est
    sauvegardée avant toute modification (avec un suffixe ``_orig``).
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
    def __init__(
        self,
        filename: str,
        *,
        colname: str,
        backup: bool = False,
        new_colname: Optional[str] = None,
    ):
        super().__init__(filename)
        self.colname = colname
        self.backup = backup
        self.new_colname = new_colname

    def apply(self, df):

        if self.backup is True and self.new_colname is not None:
            raise ImproperlyConfigured(
                "Les arguments `backup` et `new_colname` sont incompatibles."
            )

        # Check that filename and column exist
        check_filename(self.filename)
        check_columns(df, columns=self.colname)

        # Add slugname column
        tf_df = slugrot("Nom", "Prénom")
        df["fullname_slug"] = tf_df(df)

        new_column = swap_column(df, self.filename, self.colname)
        df = replace_column_aux(
            df,
            colname=self.colname,
            new_colname=self.new_colname,
            new_column=new_column,
            backup=False,
        )

        df = df.drop("fullname_slug", axis=1)
        return df


def replace_column_aux(
    df, new_colname=None, colname=None, new_column=None, backup=False
):
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
        if not isinstance(preprocessing, list):
            preprocessing = [preprocessing]

        for op in preprocessing:
            if isinstance(op, Operation):
                right_df = op.apply(right_df)
                logger.info("Preprocessing: %s", op.message())
            elif callable(op):
                if hasattr(op, "__desc__"):
                    logger.info("Preprocessing: %s", op.__desc__)
                else:
                    logger.info("Preprocessing")
                right_df = op(right_df)
            else:
                raise Exception("Unsupported preprocessing operation", op)

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
            raise Exception(f"La colonne `{right_on}` est une clé et ne peut pas être enlevée")

        right_df = right_df.drop(drop, axis=1, errors="ignore")

    # Rename columns in data to be merged
    if rename is not None:
        if right_on in rename:
            raise Exception("Pas de renommage de la clé possible")

        check_columns(right_df, rename.keys())
        right_df = right_df.rename(columns=rename)

    # Columns to drop after merge: primary key of right dataframe
    # only if name is different, _merge column added by pandas
    # during merge, programmatically added column if
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
        logger.warning(
            "Identifiant présent dans le document à aggréger "
            "mais introuvable dans le fichier central : `%s`",
            row[key],
        )

    if postprocessing is not None:
        if not isinstance(postprocessing, (list, tuple)):
            postprocessing = [postprocessing]

        for op in postprocessing:
            if isinstance(op, Operation):
                agg_df = op.apply(agg_df)
                logger.info("Postprocessing: %s", op.message())
            elif callable(op):
                if hasattr(op, "__desc__"):
                    logger.info("Postprocessing: %s", op.__desc__)
                else:
                    logger.info("Postprocessing")
                agg_df = op(agg_df)
            else:
                raise Exception("Unsupported postprocessing operation", op)

    # Try to merge columns
    for c in duplicated_columns:
        c_y = c + '_y'
        logger.warning("Fusion des colonnes `%s`", c)
        if any(agg_df[c_y].notna() & agg_df[c].notna()):
            logger.warning("Fusion impossible")
            continue

        dtype = agg_df.loc[:, c].dtype
        agg_df.loc[:, c] = agg_df.loc[:, c].fillna(agg_df.loc[:, c_y])
        new_dtype = agg_df.loc[:, c].dtype
        if new_dtype != dtype:
            logger.warning("Le type de la colonne a changé suite à la fusion: %s -> %s", dtype, new_dtype)
            try:
                logger.warning("Conversion de type")
                agg_df.loc[:, c] = agg_df[c].astype(dtype)
            except ValueError:
                logger.warning("Conversion impossible")
        drop_cols.append(c_y)

    # Drop useless columns
    agg_df = agg_df.drop(drop_cols, axis=1, errors='ignore')

    return agg_df

def read_pairs(filename):
    """Generate pairs read in `filename`."""

    with open(filename, "r") as fd:
        for line in fd:
            if line.strip().startswith("#"):
                continue
            if not line.strip():
                continue
            try:
                parts = [e.strip() for e in line.split("---")]
                stu1, stu2 = parts
                if not stu1 or not stu2:
                    raise Exception(f"Ligne incorrecte: `{line.strip()}`")
                yield stu1, stu2
            except ValueError:
                raise Exception(f"Ligne incorrecte: `{line.strip()}`")


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


def swap_column(df, filename, colname):
    """Return copy of column `colname` modified by swaps from `filename`."""

    new_column = df[colname].copy()

    for part1, part2 in read_pairs(filename):
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

    return new_column


class AggregateMoodleGrades(FileOperation):
    def apply(self, df):
        op = Aggregate(
            self.filename,
            left_on="Courriel",
            right_on="Adresse de courriel",
            drop=[
                "Prénom",
                "Nom",
                "Numéro d'identification",
                "Institution",
                "Département",
                "Total du cours (Brut)",
                "Dernier téléchargement depuis ce cours",
            ]
        )
        return op.apply(df)


class AggregateJury(FileOperation):
    def apply(self, df):
        op = Aggregate(
            self.filename,
            on="Courriel",
            subset=["Note_ECTS"]
        )
        return op.apply(df)


class Documents:
    def __init__(self, base_dir=None):
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
    """Add `func` as a method in class `cls`"""

    @functools.wraps(klass.__init__)
    def dummy(self, *args, **kwargs):
        action = klass(*args, **kwargs)
        self.add_action(action)

    dummy.__doc__ = klass.__doc__

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
    ("aggregate_moodle_grades", AggregateMoodleGrades),
    ("aggregate_jury", AggregateJury),
    ("aggregate_org", AggregateOrg),
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
