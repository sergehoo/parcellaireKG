---
name: ostack:observe
description: Sonder l'application en fonctionnement et produire des preuves.
---

# /ostack:observe

Sonder l'application en fonctionnement et produire des preuves.

## Invocation

```bash
ostack observe --gate
```

## Consigne

Confirme que le comportement réel correspond aux attentes. Cibles loopback sauf allowlist projet.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
