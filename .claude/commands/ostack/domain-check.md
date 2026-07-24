---
name: ostack:domain-check
description: Évaluer les règles métier d'un domaine sur un contexte réel.
---

# /ostack:domain-check

Évaluer les règles métier d'un domaine sur un contexte réel.

## Invocation

```bash
ostack domain check <pack.json> --action <action> --context <ctx.json> [--jurisdiction <j>]
```

## Consigne

Une règle confirmée bloque; une règle non confirmée escalade vers un humain; une règle d'une autre juridiction est exclue, jamais appliquée en silence.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
