---
name: ostack:graph
description: Reconstruire et interroger le graphe de traçabilité.
---

# /ostack:graph

Reconstruire et interroger le graphe de traçabilité.

## Invocation

```bash
ostack graph rebuild ; ostack graph unverified ; ostack graph why <id>
```

## Consigne

Sers-t'en pour savoir quel besoin justifie un fichier, quelles preuves couvrent une règle, et ce qui n'est pas prouvé.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
