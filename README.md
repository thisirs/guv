# guv

`guv` est un outil en ligne de commande d'aide à la gestion d'une ou
plusieurs UV ou UE. Il permet de centraliser les informations
concernant une UV/UE et d'en incorporer facilement de nouvelles au
travers de fichiers de configuration. Il permet entre autres de créer
des fichiers iCal, des trombinoscopes, des feuilles de présences, des
feuilles de notes...

## Installation

Il faut d'abord télécharger l'archive du projet sur Gitlab et
l'installer avec `pip` :

``` shell
pip install .
```

On peut également cloner le projet si `git` est installé comme suit :

``` shell
git clone git@gitlab.utc.fr:syrousse/guv.git
cd guv
pip install .
```

Un fichier de complétion de commandes est également disponible (voir
[ici](#fichier-de-complétion)).

## Exemple rapide

On commence par créer l'arborescence requise (voir
[ici](#création-de-larborescence) pour plus de détails) :

``` shell
guv createsemester P2021 --uv SY02,SY09
cd P2021
```

Les variables ont été renseignées dans le fichier `config.py` du
semestre.

On renseigne ensuite dans le fichier `config.py` du semestre, le
chemin relatif du fichier pdf de la liste officielle des créneaux du
semestre :

``` python
CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"
```

On peut maintenant exécuter `guv cal_uv` dans le dossier du semestre
pour générer les calendriers hebdomadaires des UV.

Voir la documentation [ici](https://www.hds.utc.fr/~syrousse/guv_bb55bc3cf80d9d2f95014408296f43f59bd3a129) pour plus de détails.
