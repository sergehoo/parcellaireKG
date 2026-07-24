---
name: ostack:intent-compile
description: Compiler un besoin en invariants, propriétés Gherkin et preuves attendues.
---

# /ostack:intent-compile

Compiler un besoin en invariants, propriétés Gherkin et preuves attendues.

## Invocation

```bash
ostack intent-compile "<besoin>"   # ou --from <draft.json> (déterministe)
```

## Consigne

Utilise-la AVANT d'implémenter. Lis les invariants et propriétés adversariales produits; ils deviennent tes critères d'acceptation.

Ajoute `--json` pour un usage automatisé. Cette commande est adossée aux moteurs déterministes d'OStack : son résultat est une preuve, pas une opinion.
