---
name: ostack:decision
description: Mémoire des décisions d'ingénierie.
---

# /ostack:decision

Mémoire des décisions d'ingénierie.

## Invocation

```bash
ostack decision search "<sujet>" ; ostack decision record <record.json>
```

## Consigne

Cherche TOUJOURS les décisions passées avant de proposer une solution. Les secrets sont masqués à l'enregistrement.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
