Modifie le fichier central avec une fonction.

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
msg : :obj:`str`, optional
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

