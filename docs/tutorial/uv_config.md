(conf-uv)=

# Configuration d'une UV

Le fichier de configuration d'une UV est situé à la racine du dossier
de l'UV/UE et contient des informations spécifiques à l'UV/UE. Il faut
obligatoirement indiquer à **guv** le chemin relatif vers le fichier
d'extraction de l'effectif de l'UV/UE (voir {ref}`ent-listing`).

Un autre fichier important est le fichier d'affectation aux
Cours/TD/TP (voir {ref}`affectation`) si il est disponible.

Il existe d'autres variables permettant d'ajouter d'autres
informations comme les informations Moodle, les changements de TD/TP
mais elles sont facultatives.

Lorsque les modifications du fichier `config.py` ont été faites, il
suffit d'exécuter la commande **guv** sans argument dans le dossier
d'UV/UE pour que les différentes informations soient incorporées à un
fichier central nommé `effectif.xlsx` (ainsi qu'une version csv)
situé à la racine du dossier d'UV/UE.

Le fichier `effectif.xlsx` est regénéré à chaque fois qu'il y a un
changement dans les dépendances. Il ne faut donc jamais y rentrer des
informations manuellement. Pour incorporer des informations, voir
{ref}`incorporation`.

(ent-listing)=

## Fichier d'extraction de l'effectif d'une UV

Le fichier de l'effectif officiel d'une UV est disponible sur l'ENT
sous la rubrique "Inscriptions aux enseignements - Liste des
étudiants inscrits" en cliquant sur "Extractions". Il s'agit d'un
fichier nommé `extraction_enseig_note.XLS` (même si c'est un
fichier csv). Il faut renseigner son chemin relatif dans la variable
`ENT_LISTING`. Il constitue la base du fichier central de l'UV
`effectif.xlsx`. Il crée les colonnes suivantes :

- `Nom`
- `Prénom`
- `Date de naissance`
- `Inscription`
- `Branche`
- `Semestre`
- `Dernier diplôme obtenu`
- `Courriel`
- `Login`
- `Tel. 1`
- `Tel. 2`

(affectation)=

## Fichier d'affectation aux Cours/TD/TP

Il s'agit du fichier fourni par l'administration qui précise les
affectations des étudiants aux différents créneaux de Cours/TD/TP. Il
est envoyé par courriel aux responsables d'UV. Il faut le copier tel
quel dans un fichier et renseigner son chemin relatif au dossier d'UV
dans la variable `AFFECTATION_LISTING`. Il est agrégé de manière
automatique au fichier central de l'UV où il crée les colonnes
suivantes :

- `Name` : Nom de l'étudiant présent dans le fichier d'affectation
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

On renseigne le chemin relatif de ce fichier dans la variable
`MOODLE_LISTING`. Une fois incorporé, ce fichier crée les colonnes
suivantes :

- `Prénom_moodle`
- `Nom_moodle`
- `Numéro d'identification`
- `Adresse de courriel`

## Fichier des tiers-temps

Il s'agit d'un simple fichier texte avec commentaire éventuel listant
ligne par ligne les étudiants bénéficiant d'un tiers-temps. Il crée la
colonne `tiers-temps` dans le fichier central `effectif.xlsx` de
l'UV.

On peut le renseigner dans la variable `TIERS_TEMPS`. Par exemple :

```shell
# Étudiants bénéficiant d'un tiers-temps
Bob Arctor
```

## Fichiers des changements de TD/TP

Il s'agit de fichiers de prise en compte des changements de groupes de
TD/TP par rapport au groupes officiels tels que décrits par le fichier
`AFFECTATION_LISTING` et présents dans les colonnes "TD" et "TP" du
fichier `effectif.xlsx`.

Chaque ligne repère un changement qui est de la forme
`id1 --- id2`. Les identifiants peuvent être des adresses courriel ou
de la forme "nom prénom". L'identifiant `id2` peut également être :

- un identifiant de séance préexistant dans la colonne (`D1`,
  `D2`, `T1`, `T2`,...) au cas où il y a un transfert et non un
  échange,
- `null` ou `nan` pour désincrire purement et simplement.

Par exemple, dans le fichier pointé par `CHANGEMENT_TD` :

```text
# Échange autorisé
Cheradenine Zakalwe --- Éléthiomel Zakalwe

# Incompatibilité Master
Mycroft Canner --- D1

# Abandon
Bob Arctor --- null
```

On peut renseigner le chemin relatif vers ces fichiers dans les
variables `CHANGEMENT_TD` et `CHANGEMENT_TP`.

## Fichier d'information générale par étudiant

Il arrive que l'on souhaite stocker d'autres informations de type
textuel sur un étudiant. On peut le renseigner dans la variable
`INFO_ETUDIANT`. C'est un fichier au format `Org` de la forme
suivante :

```text
* Nom1 Prénom1
  texte1
* Nom2 Prénom2
  texte2
```

Les informations sont incoporées dans une colonne nommée `Info`.
