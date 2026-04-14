import re
from typing import Optional

import self
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from parcelaire.models import Parcel, ParcelTag


class Command(BaseCommand):
    help = (
        "Met à jour les tags des lots du programme "
        "'LES RESIDENCES BO REFLETS' selon les plages de numéros."
    )

    PROGRAM_NAME = "LES RESIDENCES BO REFLETS"

    TAG_RULES = [
        ((1, 128), "boreflet"),
        ((130, 164), "bocenter"),
        ((167, 319), "boreal"),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--program",
            type=str,
            default=self.PROGRAM_NAME,
            help="Nom exact du programme à traiter.",
        )
        parser.add_argument(
            "--clear-existing-program-tags",
            action="store_true",
            help=(
                "Retire d'abord les tags gérés par cette commande "
                "sur les lots du programme ciblé."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les changements sans les enregistrer.",
        )

    def handle(self, *args, **options):
        program_name: str = options["program"]
        dry_run: bool = options["dry_run"]
        clear_existing_program_tags: bool = options["clear_existing_program_tags"]

        qs = (
            Parcel.objects.select_related("program")
            .prefetch_related("tags")
            .filter(program__name=program_name)
            .order_by("lot_number", "id")
        )

        total = qs.count()
        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Aucun lot trouvé pour le programme '{program_name}'."
                )
            )
            return

        managed_tags = self._get_or_build_managed_tags(dry_run=dry_run)

        updated_count = 0
        skipped_count = 0
        unmatched_count = 0

        with transaction.atomic():
            for parcel in qs:
                lot_label = (parcel.lot_number or parcel.parcel_code or "").strip()
                lot_number = self.extract_lot_number(lot_label)

                if lot_number is None:
                    unmatched_count += 1
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[SKIP] Parcel #{parcel.id} | lot='{lot_label}' | numéro introuvable"
                        )
                    )
                    continue

                target_tag_name = self.resolve_tag_name(lot_number)
                if not target_tag_name:
                    unmatched_count += 1
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[SKIP] Parcel #{parcel.id} | lot='{lot_label}' | numéro={lot_number} hors plage"
                        )
                    )
                    continue

                target_tag = managed_tags[target_tag_name]

                current_managed_tags = [
                    tag for tag in parcel.tags.all() if tag.name in managed_tags
                ]
                current_managed_names = {tag.name for tag in current_managed_tags}

                needs_update = current_managed_names != {target_tag_name}

                if not needs_update:
                    skipped_count += 1
                    self.stdout.write(
                        f"[OK] Parcel #{parcel.id} | lot='{lot_label}' | tag inchangé='{target_tag_name}'"
                    )
                    continue

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[UPDATE] Parcel #{parcel.id} | lot='{lot_label}' | numéro={lot_number} -> tag='{target_tag_name}'"
                    )
                )

                if not dry_run:
                    if clear_existing_program_tags or current_managed_tags:
                        for tag in current_managed_tags:
                            parcel.tags.remove(tag)
                    parcel.tags.add(target_tag)

                updated_count += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Terminé."))
        self.stdout.write(f"Programme ciblé : {program_name}")
        self.stdout.write(f"Lots analysés    : {total}")
        self.stdout.write(f"Mis à jour       : {updated_count}")
        self.stdout.write(f"Ignorés          : {skipped_count}")
        self.stdout.write(f"Hors règle       : {unmatched_count}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run : aucune modification enregistrée."))

    def _get_or_build_managed_tags(self, dry_run: bool) -> dict[str, ParcelTag]:
        tag_names = [tag_name for _, tag_name in self.TAG_RULES]
        result: dict[str, ParcelTag] = {}

        default_colors = {
            "boreflet": "#0ea5e9",
            "brocanter": "#f59e0b",
            "boreal": "#10b981",
        }

        for name in tag_names:
            tag = ParcelTag.objects.filter(name=name).first()
            if tag:
                result[name] = tag
                continue

            if dry_run:
                tag = ParcelTag(
                    name=name,
                    slug=slugify(name),
                    color=default_colors.get(name, "#64748b"),
                    is_active=True,
                )
            else:
                tag = ParcelTag.objects.create(
                    name=name,
                    slug=slugify(name),
                    color=default_colors.get(name, "#64748b"),
                    is_active=True,
                )

            result[name] = tag

        return result

    # Plus explicite et robuste pour l'extraction
    def extract_lot_number(self, value: str) -> Optional[int]:
        if not value:
            return None
        # Prendre le dernier segment numérique significatif (≥ 1 chiffre)
        matches = re.findall(r"(?<!\d)(\d{1,4})(?!\d)", value)
        if not matches:
            return None
        try:
            return int(matches[-1])
        except (TypeError, ValueError):
            return None

    def resolve_tag_name(self, lot_number: int) -> Optional[str]:
        for (start, end), tag_name in self.TAG_RULES:
            if start <= lot_number <= end:
                return tag_name
        return None