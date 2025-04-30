(conf-uv)=

# Configuration d'une UV

Le fichier de configuration d'une UV `config.py` est situé à la racine du
dossier de l'UV/UE et permet de générer un fichier `effectif.xlsx` qui regroupe
toutes les données sur l'effectif de cette UV (Nom, groupes de TD/TP,
notes,...).

On peut y ajouter des informations en appelant des fonctions sur un objet
s'appelant `DOCS` de type `Documents`.

```python
from guv.helpers import Documents

DOCS = Documents()

DOCS.une_fonction(...)
DOCS.une_autre_fonction(...)
```

Lorsque les modifications du fichier `config.py` ont été faites, il suffit
d'exécuter la commande **guv** sans argument dans le dossier d'UV/UE pour que
les différentes informations soient incorporées à `effectif.xlsx` (ainsi qu'une
version csv) situé à la racine du dossier d'UV/UE.

Le fichier `effectif.xlsx` est regénéré à chaque fois qu'il y a un changement
dans les déclarations de `DOCS`. Il ne faut donc jamais y rentrer des
informations manuellement.

(ent-listing)=

## Fichier d'extraction de l'effectif d'une UV

Le fichier de l'effectif officiel d'une UV est disponible sur l'ENT sous la
rubrique "Liste des étudiants inscrits à une UV" en cliquant sur "Extractions".
Il faut utiliser la fonction `add_utc_ent_listing` :

```python
DOCS.add_utc_ent_listing("documents/SY09.xls")
```

Il crée les colonnes suivantes :

- `Nom`
- `Prénom`
- `Date de naissance`
- `Dernier diplôme`
- `Courriel`
- `Login`
- `Branche`
- `Semestre`

(affectation)=

## Fichier d'affectation aux Cours/TD/TP

Il s'agit du fichier fourni par l'administration qui précise les
affectations des étudiants aux différents créneaux de Cours/TD/TP. Il
est envoyé par courriel aux responsables d'UV. Il faut le copier tel
quel dans un fichier et renseigner son chemin relatif au dossier d'UV
dans `DOCS.add_affectation("...")`. Il est agrégé de manière
automatique au fichier central de l'UV où il crée les colonnes
suivantes :

- `Cours` : Groupe de cours (`C`, `C1`, `C2`)
- `TD` : Groupe de TD (`D1`, `D2`,...)
- `TP` : Groupe de TP (`T1`, `T2`, `T1A`, `T1B`,...)

De part sa nature, son agrégation peut donner lieu à des ambiguïtés
qui sont levées en interrogeant l'utilisateur (choix semaine A/B, nom
d'étudiant non reconnu).

(moodle-listing)=

## Fichier de l'effectif de Moodle

Des renseignements supplémentaires sont disponibles sur Moodle :
l'identifiant de connexion, le numéro d'identification, l'adresse
courriel (qui peut différer de l'adresse figurant dans l'effectif
officiel). Ces informations sont disponibles en exportant sous Moodle
une feuille de note (en plus des notes qui ne nous intéresse pas). Il
faut aller dans `Configuration du carnet de notes` et sélectionner
`Feuille de calcul Excel` dans le menu déroulant et ensuite
`Télécharger`.

On renseigne le chemin relatif de ce fichier comme suit :

```python
DOCS.add_moodle_listing("documents/SY09_Notes.xlsx")
```

Une fois incorporé, ce fichier crée les colonnes suivantes :

- `Prénom_moodle`
- `Nom_moodle`
- `Numéro d'identification`
- `Adresse de courriel`

## Fichiers des changements de TD/TP

Pour faciliter les changements de groupes de TD/TP, on peut utiliser la function
`switch`.

```python
DOCS.switch("documents/changement_TD", colname="TD")
```

Chaque ligne du fichier repère un changement qui est de la forme `id1 --- id2`.
Les identifiants peuvent être des adresses courriel ou de la forme "nom prénom".
L'identifiant `id2` peut également être :

- un identifiant de séance préexistant dans la colonne (`D1`, `D2`, `T1`,
  `T2`,...) au cas où il y a un transfert et non un échange,

- `null` ou `nan` pour désinscrire purement et simplement.

Par exemple, dans le fichier `documents/changement_TD` on peut trouver :

```text
# Échange autorisé
Cheradenine Zakalwe --- Éléthiomel Zakalwe

# Incompatibilité Master
Mycroft Canner --- D1

# Abandon
Bob Arctor --- null
```
