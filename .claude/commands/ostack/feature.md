---
name: ostack:feature
description: Dérouler le workflow vérifié complet d'une fonctionnalité.
---

# /ostack:feature

Dérouler le workflow vérifié complet d'une fonctionnalité.

## Invocation

```bash
ostack feature "<besoin>" --provider <ollama|openai|anthropic>
```

## Consigne

Le workflow s'arrête à chaque barrière humaine et donne la commande de reprise. Utilise --provider mock pour un essai déterministe.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
