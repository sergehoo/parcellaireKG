---
name: ostack:verify
description: Rendre un verdict de release fondé sur les preuves.
---

# /ostack:verify

Rendre un verdict de release fondé sur les preuves.

## Invocation

```bash
ostack verify <evidence-input.json> --gate
```

## Consigne

`--gate` échoue si le budget qualité ou la Definition of Done n'est pas atteint. Ne contourne jamais un échec de gate.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
