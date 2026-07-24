---
name: ostack:prove
description: Assembler et sceller l'Evidence Pack d'une tâche.
---

# /ostack:prove

Assembler et sceller l'Evidence Pack d'une tâche.

## Invocation

```bash
ostack prove <evidence-input.json>
```

## Consigne

Renseigne uniquement des observations RÉELLEMENT exécutées (tests, sécurité, perf). Le statut VERIFIED est refusé si une preuve manque.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
