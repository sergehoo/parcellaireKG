---
name: ostack:architecture-check
description: Vérifier les frontières d'architecture contre le graphe d'imports réel.
---

# /ostack:architecture-check

Vérifier les frontières d'architecture contre le graphe d'imports réel.

## Invocation

```bash
ostack architecture check --gate
```

## Consigne

Toute dépendance interdite est un blocage de merge. Corrige l'import, ne désactive pas la règle.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
