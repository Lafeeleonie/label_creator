# Editeur d'etiquettes electronique

Interface Streamlit pour composer des etiquettes d'atelier electronique et exporter un PDF imprimable aux dimensions exactes.

Par defaut, le format est regle sur des etiquettes de `12,5 x 10 mm`, organisees sur A4 en `16 x 29` etiquettes sans espace.

L'interface utilise un theme sombre par defaut.

## Lancement

Double-cliquer sur `lancer_streamlit.bat`.

Le script cree ou reutilise `.venv`, installe les dependances et lance Streamlit sur :

```text
http://127.0.0.1:8585
```

## Impression

Le PDF est genere avec ReportLab en millimetres. Dans la fenetre d'impression, choisir `Taille reelle`, `100 %` ou `Aucune mise a l'echelle` pour conserver les dimensions des etiquettes.

## Symboles

L'interface contient une banque de symboles electroniques et une banque de vis. Les symboles de vis sont rendus simplement sous la forme `M2`, `M3`, `M4`, etc.
