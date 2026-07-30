# OStack — Evidence Pack du Copilote IA

> Exigé par `CLAUDE.md` : « toute affirmation de réussite doit être adossée à une
> preuve exécutée via la commande `ostack` ». Ce document résume l'Evidence Pack
> **scellé** pour la fonctionnalité `ai_copilot` (branche `feat/ai-copilot`).

- **Entrée** : [`ostack-evidence-copilot.json`](../../ostack-evidence-copilot.json)
- **Pack scellé** : [`copilot-evidence-pack.json`](copilot-evidence-pack.json) (via `ostack prove`)
- **Journal** : `.ostack/audit.jsonl` → `evidence.persist: succeeded`

## Verdict de release (`ostack verify --gate`)

```
Release gate failed (BLOCK): unmitigated high risk:
Secrets réels extractibles de l'historique git (SECRET_KEY, DB_PASSWORD, EXTERNAL_LOTS_API_*)
```

**BLOCK** est le verdict **correct et attendu** : la fonctionnalité n'est pas
livrable tant que (1) l'opérateur n'a pas roté les secrets + purgé l'historique
git, et (2) une approbation humaine de release n'a pas été enregistrée. Le code
du Copilote, lui, est prouvé (tests exécutés, invariants sécurité vérifiés).

## Confiance multidimensionnelle (`ostack confidence`) — global **69/100**

| Dimension | Score | Appui |
|-----------|:-----:|-------|
| requirements_understanding | 88 | invariant confirmation (jeton signé) |
| implementation_correctness | 88 | build, `manage.py check`, PostGIS |
| test_strength | 82 | 187 tests, 0 échec |
| security_assurance | 80 | tests permission SQL/PII, revues adversariales |
| performance_assurance | 45 | *non mesurée* (risque résiduel) |
| documentation_consistency | 92 | DEPLOYMENT.md §8, .env.example, README |
| rollback_readiness | 50 | *approbation humaine absente* |

## Preuves exécutées (extrait)

- **187 tests**, 0 échec (dont 67 `ai_copilot`) sur base **PostGIS réelle**.
- **Build front** Vite OK ; `manage.py check` : 0 problème.
- **Permissions** : agent SQL refuse DELETE/DDL, tables hors whitelist, **jointure
  virgule** et **sous-requête `auth_user`** ; PII masquée sans droit (recherche
  client, digest analytics).
- **Invariant action** : effet de bord exige un **jeton signé** (forgé / lié à un
  autre utilisateur → refusés) ; exécution déterministe **hors-LLM**.
- **PostGIS** : `parcels_near_place` — sémantique **métrique** vérifiée (~80 m
  inclus, ~70 km exclu à 1 km).
- **Revues adversariales** : 0 critique/haut ; **2 findings hauts** détectés à
  l'audit puis **corrigés** (fuite PII digest, bypass whitelist SQL).

## Pour lever le BLOCK (conditions de release)

1. **Opérateur** : roter tous les secrets historiques + `git filter-repo` + force-push.
2. **Gouvernance** : décision sur l'egress PII/financier vers LLM tiers (base légale + fournisseur zero-retention).
3. **Approbation humaine** de release enregistrée (`humanApprovals`), puis merge de `feat/ai-copilot`.

Régénérer : `ostack prove ostack-evidence-copilot.json` puis `ostack verify ostack-evidence-copilot.json --gate`.
