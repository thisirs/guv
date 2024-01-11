# Changement des chemins par défaut

Beaucoup de tâches écrivent des fichiers avec un nom prédéfini dans un
dossier prédéfini. Il est possible de changer ces valeurs par défaut en
utilisant les attributs de classe `target_name` et `target_dir` de
la tâche correspondante. Par exemple, la tâche `XlsStudentDataMerge`
est responsable de la création du fichier `effectifs.xlsx` dans le
dossier de l'UV.

Pour changer cela, on peut écrire le code suivant dans le fichier
`config.py` de l'UV :

```python
from guv.tasks import XlsStudentDataMerge
XlsStudentDataMerge.target_name = "info.xlsx"
XlsStudentDataMerge.target_dir = "documents"
```

L'effectif sera alors écrit dans le dossier `documents` avec le nom
`info.xlsx`.
