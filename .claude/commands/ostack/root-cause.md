---
name: ostack:root-cause
description: Analyse de cause racine structurée sur le journal d'audit.
---

# /ostack:root-cause

Analyse de cause racine structurée sur le journal d'audit.

## Invocation

```bash
ostack root-cause open --incident <id> --symptom "<symptôme>"
```

## Consigne

Distingue symptôme, cause directe, cause racine, correction, prévention. Le statut 'diagnosed' exige une expérience concluante ET un test de non-régression.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
