# guv

`guv` est un outil en ligne de commande d'aide à la gestion d'une ou
plusieurs UV ou UE. Il permet de centraliser les informations
concernant une UV/UE et d'en incorporer facilement de nouvelles au
travers de fichiers de configuration. Il permet entre autres de créer
des fichiers iCal, des trombinoscopes, des feuilles de présences, des
feuilles de notes...

## Installation

`guv` est installable directement via `pip` :

``` shell
pip install guv --extra-index-url https://<identifiant>:<mot_de_passe>@gitlab.utc.fr/api/v4/projects/9255/packages/pypi/simple
```

Il faut remplacer `<identifiant>` par votre identifiant ENT et `<mot_de_passe>`
par le mot de passe correspondant.

On peut également cloner le projet avec `git` et ensuite l'installer comme
suit :

``` shell
git clone git@gitlab.utc.fr:syrousse/guv.git
cd guv
pip install .
```

## Exemple rapide

On commence par créer l'arborescence requise :

``` shell
guv createsemester P2022 --uv SY02 SY09
cd P2022
```

Les variables ont été renseignées dans le fichier `config.py` du
semestre.

On renseigne ensuite dans le fichier `config.py` du semestre, le
chemin relatif du fichier pdf de la liste officielle des créneaux du
semestre disponible
[ici](https://webapplis.utc.fr/ent/services/services.jsf?sid=578) :

``` python
CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"
```

On peut maintenant exécuter ``guv cal_uv`` dans le dossier ``P2022``
pour générer les calendriers hebdomadaires des UV ou bien ``guv
ical_uv`` pour générer des fichiers iCal de tous les créneaux.

Voir la documentation [ici](https://syrousse.gitlab.utc.fr/guv/) pour
plus de détails.
