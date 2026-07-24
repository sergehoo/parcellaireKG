---
name: ostack:performance
description: Établir une baseline et détecter les régressions de performance.
---

# /ostack:performance

Établir une baseline et détecter les régressions de performance.

## Invocation

```bash
ostack performance baseline --samples 10 ; ostack performance compare --gate
```

## Consigne

Une régression p95 au-delà du budget bloque la release. Mesure sur l'application réellement lancée.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
