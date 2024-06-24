(incorporation)=

# Incorporation d'informations extérieures

Les informations concernant l'effectif d'une UV sont toutes
rassemblées dans un fichier central Excel situé à la racine de l'UV :
`effectif.xlsx`. Un certain nombre d'informations y sont déjà
incorporées automatiquement : l'effectif officiel via la variable
`ENT_LISTING`, les affectations au Cours/TD/TP ainsi que les données
Moodle, les tiers-temps, les changements de TD/TP et les informations
par étudiant si elles ont été renseignées dans les variables
correspondantes.

Il arrive qu'on dispose d'informations extérieures concernant les
étudiants (feuilles de notes Excel/csv, fichier csv de groupes
provenant de Moodle ou généré avec **guv**,...) et qu'on veuille les
incorporer au fichier central de l'UV. Pour cela, il faut décrire les
agrégations dans le fichier de configuration d'UV/UE à l'aide d'un
objet de type `Documents` impérativement appelé `DOCS` :

```python
from guv.helpers import Documents
DOCS = Documents()
```

Pour déclarer une incorporation, on utiliser la méthode `add` sur
`DOCS` :

```{eval-rst}
.. automethod:: guv.helpers.Documents.add
```

À la prochaine exécution de **guv** sans argument, la tâche par défaut
va reconstruire le fichier central et le fichier `notes.csv` sera
incorporé. Il reste à implémenter `fonction_qui_incorpore` qui
réalise l'incorporation. Cependant pour la plupart des usages, il
existe des fonctions spécialisées suivant le type d'information à
incorporer.

Pour incorporer des fichiers sous forme de tableau csv/Excel, on
utilise `aggregate`. On a alors

```python
DOCS.aggregate("documents/notes.csv", on="Courriel")
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate
```

Lorsque les fichiers sont encore plus spécifiques, on peut utiliser
les fonctions suivantes :

- Pour un fichier de notes issu de Moodle :

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.aggregate_moodle_grades
  ```

- Pour un fichier de jury issu de la tâche
  {class}`~guv.tasks.gradebook.XlsGradeBookJury`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.aggregate_jury
  ```

- Pour un fichier issu de Wexam

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.aggregate_wexam_grades
  ```

Pour incorporer des fichiers au format Org, on utilise
`aggregate_org` :

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_org
```

Pour créer/modifier le fichier central sans utiliser de fichier tiers,
on peut utiliser les fonctions suivantes :

- Fonction `fillna_column`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.fillna_column
  ```

- Fonction `replace_regex`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.replace_regex
  ```

- Fonction `replace_column`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.replace_column
  ```

- Fonction `flag`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.flag
  ```

- Fonction `switch`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.switch
  ```

- Fonction `apply_df`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.apply_df
  ```

- Fonction `apply_column`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.apply_column
  ```

- Fonction `apply_cell`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.apply_cell
  ```

- Fonction `compute_new_column`

  ```{eval-rst}
  .. automethod:: guv.helpers.Documents.compute_new_column
  ```

Une dernière possibilité est la fonction `aggregate_self` qui permet de garder
les colonnes qui ont été modifiées manuellement dans le fichier central.

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_self
```
