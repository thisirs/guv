(conf-semester)=

# Configuration du semestre

Le fichier de configuration du semestre contient des informations
spécifiques à un semestre :

- liste des UV/UE gérées via la variable `UVS`,
- chemin vers le fichier des créneaux fourni par l'administration, via
  la variable `CRENEAU_UV`,
- liste des plannings via la variable `PLANNINGS`,

(conf-creneau)=

## Configuration des créneaux

Pour que **guv** ait connaissance des créneaux des UV, il faut lui donner accès
au fichier pdf fourni par l'administration. Si l'arborescence a été créée avec
la tâche `createsemester` et un nom de semestre reconnu par **guv** (de type
A2021, P2022,...) la variable `CRENEAU_UV` est automatiquement renseignée et
pointe vers le fichier officiel des créneaux placé dans le sous-dossier
`documents`. Sinon, il faut le télécharger
[ici](https://webapplis.utc.fr/ent/services/services.jsf?sid=578) et renseigner
la variable `CRENEAU_UV` pour qu'elle pointe vers ce fichier.

## Configuration des plannings avec `PLANNINGS`

Si l'arborescence a été créée avec la tâche `createsemester` et un
nom de semestre reconnu par **guv** (de type A2021, P2022,...) la
variable `PLANNINGS` est automatiquement renseignée. Si en plus
les dossiers d'UV ont été créés avec l'option `--uv`, la variable
`UVS` est aussi renseignée et on peut sauter cette section.

Les plannings sont des périodes de temps sur un même semestre. Par
défaut, le planning ingénieur, qui porte le même nom que le semestre
est utilisé. Il est possible de configurer d'autres périodes de temps
pour un même semestre (pour gérer les trimestres des masters par
exemple).

La déclaration des plannings est contrôlée par la variable
`PLANNINGS` qui est un dictionnaire dont les clés sont le nom des
plannings à paramétrer et les valeurs un dictionnaire de
caractéristiques.

Les caractéristiques nécessaires pour définir un planning sont :

- `UVS` : la liste des UV gérées par ce planning,
- `PL_BEG` : la date de début de planning
- `PL_END` : la date de fin de planning
- `SKIP_DAYS_C` : la liste des jours où il n'y a pas de cours
- `SKIP_DAYS_D` : la liste des jours où il n'y a pas de TD
- `SKIP_DAYS_T` : la liste des jours où il n'y a pas de TP
- `TURN` : un dictionnaire des jours transformés en d'autres jours
  (jours fériés ou journées spéciales).

En utilisant les fonctions d'aide `skip_range` et `skip_week`, on
peut définir par exemple :

```python
from guv.helpers import skip_range
from datetime import date

ferie = [
    date(2022, 5, 26),
    date(2022, 6, 6),
    date(2022, 4, 18)
]
debut = skip_range(date(2022, 2, 21), date(2022, 2, 26))
vacances_printemps = skip_range(date(2022, 4, 11), date(2022, 4, 16))
median = skip_range(date(2022, 4, 19), date(2022, 4, 25))
final = skip_range(date(2022, 6, 16), date(2022, 6, 25))

PLANNINGS = {
    "P2022": {
        "UVS": ["SY02", "SY09"],
        "PL_BEG": date(2022, 2, 21),
        "PL_END": date(2022, 6, 25),
        "SKIP_DAYS_C": ferie + vacances_printemps + median + final,
        "SKIP_DAYS_D": ferie + vacances_printemps + debut + median + final,
        "SKIP_DAYS_T": ferie + vacances_printemps + debut + final,
        "TURN": {
            date(2022, 5, 24): "Jeudi",
            date(2022, 6, 8): "Lundi"
        }
    }
}
```
