(creation-de-larborescence)=

# Création de l'arborescence

**guv** travaille avec une arborescence prédéfinie. Les documents
spécifiques à une UV sont stockées dans un dossier d'UV. Tous les
dossiers d'UV sont stockés dans un dossier de semestre. Chaque dossier
d'UV contient un fichier nommé `config.py` pour configurer l'UV. Le
dossier de semestre contient également un dossier de configuration nommé
`config.py`.

Pour créer cette arborescence ainsi que les fichiers de configuration
préremplis on peut exécuter la commande suivante :

```bash
guv createsemester P2022 --uv SY02 SY09
```

qui va créer un dossier de semestre nommé `P2022` contenant un
fichier de configuration prérempli `config.py` (voir
{ref}`conf-semester` pour sa configuration) ainsi que des
sous-dossiers `generated` et `documents` et deux autres dossiers
d'UV nommés `SY02` et `SY09` contenant chacun leur fichier de
configuration prérempli également nommé `config.py` (voir
{ref}`conf-UV` pour sa configuration) ainsi que des sous-dossiers
`generated` et `documents`. L'arborescence est alors la suivante :

```shell
P2022
├── config.py
├── documents
├── generated
├── SY02
│   ├── config.py
│   ├── documents
│   └── generated
└── SY09
    ├── config.py
    ├── documents
    └── generated
```

Si on veut rajouter des dossiers d'UV à un dossier de semestre déjà
existant, on peut exécuter la commande suivante à l'intérieur d'un
dossier de semestre:

```bash
cd P2022
guv createuv SY19 AOS1
```

Pour que l'UV soit effectivement prise en compte par **guv**, il faut
ensuite la déclarer dans le fichier `config.py` du semestre avec
la variable `UVS` et lui associer un planning dans `PLANNINGS`.
