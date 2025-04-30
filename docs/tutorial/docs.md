(incorporation)=

# Agrégation d'informations au fichier central `effectif.xlsx`

Les informations concernant l'effectif d'une UV sont toutes
rassemblées dans un fichier central Excel situé à la racine de l'UV :
`effectif.xlsx`.

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

## Agrégation de documents fournis

```{eval-rst}
.. automethod:: guv.helpers.Documents.add_utc_ent_listing
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.add_affectation
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_amenagements
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.add_moodle_listing
```

## Agrégation de documents extérieurs

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_moodle_grades
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_moodle_groups
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_wexam_grades
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_jury
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_self
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.aggregate_org
```

## Modification directe du fichier `effectif.xlsx`

```{eval-rst}
.. automethod:: guv.helpers.Documents.flag
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.apply_cell
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.compute_new_column
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.switch
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.fillna_column
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.replace_regex
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.replace_column
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.apply_column
```

## Modification globale du fichier `effectif.xlsx`

```{eval-rst}
.. automethod:: guv.helpers.Documents.add
```

```{eval-rst}
.. automethod:: guv.helpers.Documents.apply_df
```
