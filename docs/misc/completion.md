
(fichier-de-completion)=

# Fichier de complétion

Des fichiers de complétion pour `zsh` et `bash` sont disponibles
dans le sous-dossier `data`. Pour un système type Unix et le shell
`zsh`, on peut utiliser les commandes suivantes :

```bash
mkdir -p ~/.zsh/completions
cp $(python -c "import guv; print(guv.__path__[0])")/data/_guv_zsh ~/.zsh/completions/_guv
```

Si des tâches supplémentaires ont été ajoutées avec la variable
`TASKS`, il est possible de mettre à jour les fichiers de complétion.
Il faut d'abord installer la bibliothèque `shtab` et exécuter la
commande suivante dans le dossier du semestre.

```bash
python -c "from guv.runner import print_completer; print_completer(shell='zsh')" > ~/.zsh/completions/_guv
```
