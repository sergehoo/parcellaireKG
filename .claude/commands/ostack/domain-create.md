---
name: ostack:domain-create
description: Créer un Domain Pack métier à partir de sources.
---

# /ostack:domain-create

Créer un Domain Pack métier à partir de sources.

## Invocation

```bash
ostack domain create --name <id> --sources <dossier>
```

## Consigne

Le pack naît au niveau 0 (inconnu). Renseigne glossaire, acteurs, règles depuis les sources, puis fais valider par un expert. Ne prétends jamais connaître le métier sans sources.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
