# Editeur d'etiquettes electronique

Interface Streamlit pour composer des etiquettes d'atelier electronique et exporter un PDF imprimable aux dimensions exactes.

Les valeurs par defaut sont dans `config.toml` : page A4, marges minimales de `10 mm`, etiquettes de `12,5 x 10 mm` et aucun espacement.

Le nombre de lignes et de colonnes est calcule automatiquement pour ne garder que des etiquettes completes. Si de la place reste sur la page, elle est ajoutee aux marges finales pour centrer la grille.

L'interface utilise un theme sombre par defaut.

La quantite par defaut d'une ligne d'etiquette est `1`.

## Lancement

Double-cliquer sur `lancer_streamlit.bat`.

Le script cree ou reutilise `.venv`, installe les dependances et lance Streamlit sur :

```text
http://127.0.0.1:8585
```

## Impression

Le PDF est genere avec ReportLab en millimetres. Dans la fenetre d'impression, choisir `Taille reelle`, `100 %` ou `Aucune mise a l'echelle` pour conserver les dimensions des etiquettes.

L'aperçu integre le PDF reel genere par l'application.

## Symboles

L'interface contient une banque de symboles electroniques et une banque de vis. Les symboles de vis sont rendus simplement sous la forme `M2`, `M3`, `M4`, etc.

Sur les etiquettes, le symbole est place au-dessus du texte.
