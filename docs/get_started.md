# Introduction

**guv** est un outil en ligne de commande d'aide à la gestion d'une ou
plusieurs UV ou UE. Il permet de centraliser les informations concernant
une UV/UE et d'en incorporer facilement de nouvelles au travers de
fichiers de configuration. Il permet entre autres de créer des fichiers
iCal, des trombinoscopes, des feuilles de présences, des feuilles de
notes...

## Installation

**guv** est installable directement via `pip` :

```bash
pip install guv --index-url https://gitlab.utc.fr/api/v4/projects/9255/packages/pypi/simple
```

## Exemple rapide

On commence par créer l'arborescence requise avec la sous-commande
`createsemester` (voir {ref}`creation-de-larborescence` pour plus de
détails). Par exemple :

```bash
guv createsemester P2022 --uv SY02 SY09
cd P2022
```

Le fichier `config.py` du semestre est déjà pré-rempli avec les données du
semestre correspondant et les UVs fournies.

On renseigne ensuite dans ce même fichier, le chemin relatif du fichier pdf de
la liste officielle des créneaux du semestre disponible [ici](https://webapplis.utc.fr/ent/services/services.jsf?sid=578). Si on le place
dans le sous-dossier `documents`, on écrit :

```python
CRENEAU_UV = "documents/Creneaux-UV-hybride-prov-V02.pdf"
```

On peut maintenant exécuter `guv cal_uv` dans le dossier `P2022`
pour générer les calendriers hebdomadaires des UV ou bien `guv
ical_uv` pour générer des fichiers iCal de tous les créneaux.
