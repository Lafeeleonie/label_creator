# Editeur d'etiquettes electronique

Interface Streamlit pour composer des etiquettes d'atelier electronique et exporter un PDF imprimable aux dimensions exactes.

## Lancement

Double-cliquer sur `lancer_streamlit.bat`.

Le script cree ou reutilise `.venv`, installe les dependances et lance Streamlit sur :

```text
http://127.0.0.1:8585
```

## Impression

Le PDF est genere avec ReportLab en millimetres. Dans la fenetre d'impression, choisir `Taille reelle`, `100 %` ou `Aucune mise a l'echelle` pour conserver les dimensions des etiquettes.

## Git

`instruction.md` et `.venv/` sont ignores par Git.

