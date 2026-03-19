# # /Users/ogahserge/Documents/parcelaireKG/parcelaire/management/commands/import_parcellaire_geojson.py
# import json
# from decimal import Decimal
#
# from django.core.management.base import BaseCommand, CommandError
# from django.contrib.gis.geos import GEOSGeometry, Point
# from django.db import transaction
# from django.utils.text import slugify
#
# from parcelaire.models import (
#     Country,
#     Place,
#     ProjetImmobilier,
#     RealEstateProgram,
#     ProgramPhase,
#     ParcelDataset,
#     ProgramBlock,
#     Parcel,
# )
#
#
# class Command(BaseCommand):
#     help = "Importe un fichier GeoJSON parcellaire dans la base"
#
#     def add_arguments(self, parser):
#         parser.add_argument("--file", type=str, required=True, help="Chemin du fichier GeoJSON")
#         parser.add_argument("--country", type=str, required=True, help="Nom du pays")
#         parser.add_argument("--project-code", type=str, required=True, help="Code du projet immobilier")
#         parser.add_argument("--project-name", type=str, required=True, help="Nom du projet immobilier")
#         parser.add_argument("--program-code", type=str, required=True, help="Code du programme immobilier")
#         parser.add_argument("--program-name", type=str, required=True, help="Nom du programme immobilier")
#         parser.add_argument("--phase-code", type=str, help="Code de la phase")
#         parser.add_argument("--phase-name", type=str, help="Nom de la phase")
#         parser.add_argument("--place-id", type=int, help="ID du lieu Place")
#         parser.add_argument("--dataset-name", type=str, help="Nom du dataset")
#         parser.add_argument("--replace", action="store_true", help="Supprime les parcelles du dataset courant avant import")
#
#     @transaction.atomic
#     def handle(self, *args, **options):
#         file_path = options["file"]
#
#         try:
#             with open(file_path, "r", encoding="utf-8") as f:
#                 geojson = json.load(f)
#         except FileNotFoundError:
#             raise CommandError(f"Fichier introuvable : {file_path}")
#         except json.JSONDecodeError as e:
#             raise CommandError(f"JSON invalide : {e}")
#
#         if geojson.get("type") != "FeatureCollection":
#             raise CommandError("Le fichier doit être un GeoJSON de type FeatureCollection.")
#
#         country_name = options["country"]
#         project_code = options["project_code"]
#         project_name = options["project_name"]
#         program_code = options["program_code"]
#         program_name = options["program_name"]
#         phase_code = options.get("phase_code")
#         phase_name = options.get("phase_name")
#         place_id = options.get("place_id")
#
#         dataset_name = options.get("dataset_name") or geojson.get("name") or "Import parcellaire"
#
#         country, _ = Country.objects.get_or_create(
#             nom=country_name
#         )
#
#         place = None
#         if place_id:
#             try:
#                 place = Place.objects.get(pk=place_id)
#             except Place.DoesNotExist:
#                 raise CommandError(f"Aucun Place trouvé avec l'id={place_id}")
#
#             if place.country_id != country.id:
#                 raise CommandError("Le Place fourni n'appartient pas au pays sélectionné.")
#
#         project, _ = ProjetImmobilier.objects.get_or_create(
#             code=project_code,
#             defaults={
#                 "nom": project_name,
#                 "slug": slugify(project_name),
#                 "country": country,
#                 "place": place,
#             }
#         )
#
#         updated_project = False
#         if project.nom != project_name:
#             project.nom = project_name
#             updated_project = True
#         if not project.slug:
#             project.slug = slugify(project_name)
#             updated_project = True
#         if project.country_id != country.id:
#             project.country = country
#             updated_project = True
#         if place and project.place_id != place.id:
#             project.place = place
#             updated_project = True
#         if updated_project:
#             project.save()
#
#         program, _ = RealEstateProgram.objects.get_or_create(
#             code=program_code,
#             defaults={
#                 "name": program_name,
#                 "slug": slugify(program_name),
#                 "country": country,
#                 "place": place,
#                 "project": project,
#             }
#         )
#
#         updated_program = False
#         if program.name != program_name:
#             program.name = program_name
#             updated_program = True
#         if not program.slug:
#             program.slug = slugify(program_name)
#             updated_program = True
#         if program.country_id != country.id:
#             program.country = country
#             updated_program = True
#         if place and program.place_id != place.id:
#             program.place = place
#             updated_program = True
#         if program.project_id != project.id:
#             program.project = project
#             updated_program = True
#         if updated_program:
#             program.save()
#
#         phase = None
#         if phase_code and phase_name:
#             phase, _ = ProgramPhase.objects.get_or_create(
#                 program=program,
#                 code=phase_code,
#                 defaults={
#                     "name": phase_name,
#                     "order": 1,
#                 }
#             )
#             if phase.name != phase_name:
#                 phase.name = phase_name
#                 phase.save()
#
#         dataset, created = ParcelDataset.objects.get_or_create(
#             program=program,
#             phase=phase,
#             name=dataset_name,
#             defaults={
#                 "source_code": geojson.get("name"),
#                 "source_file_name": file_path.split("/")[-1],
#                 "geojson_type": geojson.get("type", "FeatureCollection"),
#                 "crs_name": ((geojson.get("crs") or {}).get("properties") or {}).get("name"),
#                 "xy_coordinate_resolution": geojson.get("xy_coordinate_resolution"),
#                 "version": "1.0",
#                 "is_current": True,
#             }
#         )
#
#         if not created:
#             dataset.source_code = geojson.get("name")
#             dataset.source_file_name = file_path.split("/")[-1]
#             dataset.geojson_type = geojson.get("type", "FeatureCollection")
#             dataset.crs_name = ((geojson.get("crs") or {}).get("properties") or {}).get("name")
#             dataset.xy_coordinate_resolution = geojson.get("xy_coordinate_resolution")
#             dataset.save()
#
#         if options["replace"]:
#             deleted_count, _ = Parcel.objects.filter(dataset=dataset).delete()
#             self.stdout.write(self.style.WARNING(f"{deleted_count} parcelle(s) supprimée(s) avant réimport."))
#
#         features = geojson.get("features", [])
#         if not features:
#             raise CommandError("Aucune feature trouvée dans le GeoJSON.")
#
#         blocks_cache = {}
#         created_blocks = 0
#         created_parcels = 0
#         updated_parcels = 0
#         skipped_empty_geometry = 0
#
#         for feature in features:
#             properties = feature.get("properties", {}) or {}
#             geometry = feature.get("geometry", {}) or {}
#
#             fid = properties.get("fid")
#             lot_number = properties.get("LOT_NOM")
#             ilot_code = properties.get("ILOT_NOM")
#             area = properties.get("Area")
#
#             block = None
#             if ilot_code:
#                 if ilot_code not in blocks_cache:
#                     block, block_created = ProgramBlock.objects.get_or_create(
#                         program=program,
#                         code=str(ilot_code),
#                         defaults={
#                             "label": f"Îlot {ilot_code}",
#                             "phase": phase,
#                         }
#                     )
#                     if not block_created:
#                         updated = False
#                         if phase and block.phase_id != phase.id:
#                             block.phase = phase
#                             updated = True
#                         if not block.label:
#                             block.label = f"Îlot {ilot_code}"
#                             updated = True
#                         if updated:
#                             block.save()
#                     else:
#                         created_blocks += 1
#
#                     blocks_cache[ilot_code] = block
#
#                 block = blocks_cache[ilot_code]
#
#             geom_obj = None
#             centroid = None
#
#             coords = geometry.get("coordinates")
#             if geometry.get("type") and coords:
#                 try:
#                     geom_obj = GEOSGeometry(json.dumps(geometry), srid=4326)
#                     # geom_obj = geom_obj.force_3d()
#                     centroid = geom_obj.centroid if geom_obj and not geom_obj.empty else None
#                 except Exception as e:
#                     self.stdout.write(self.style.WARNING(
#                         f"Feature fid={fid}: géométrie invalide ignorée ({e})"
#                     ))
#             else:
#                 skipped_empty_geometry += 1
#
#             defaults = {
#                 "program": program,
#                 "phase": phase,
#                 "block": block,
#                 "source_fid": fid,
#                 "lot_number": str(lot_number) if lot_number is not None else None,
#                 "parcel_code": f"{ilot_code}-{lot_number}" if ilot_code and lot_number else None,
#                 "official_area_m2": Decimal(str(area)) if area is not None else None,
#                 "computed_area_m2": Decimal(str(area)) if area is not None else None,
#                 "geometry": geom_obj,
#                 "centroid": centroid,
#                 "geometry_valid": bool(geom_obj),
#                 "has_number": lot_number is not None,
#                 "duplicate_flag": False,
#                 "metadata": {
#                     "source_properties": properties,
#                 },
#             }
#
#             parcel_qs = Parcel.objects.filter(dataset=dataset, source_fid=fid)
#             if parcel_qs.exists():
#                 parcel = parcel_qs.first()
#                 for field, value in defaults.items():
#                     setattr(parcel, field, value)
#                 parcel.save()
#                 updated_parcels += 1
#             else:
#                 Parcel.objects.create(
#                     dataset=dataset,
#                     **defaults
#                 )
#                 created_parcels += 1
#
#         program.estimated_lot_count = Parcel.objects.filter(program=program).count()
#
#         total_area = (
#             Parcel.objects.filter(program=program)
#             .exclude(official_area_m2__isnull=True)
#             .values_list("official_area_m2", flat=True)
#         )
#         total_area_sum = sum(total_area) if total_area else Decimal("0")
#         program.total_area_m2 = total_area_sum
#         program.save()
#
#         self.stdout.write(self.style.SUCCESS("Import terminé avec succès."))
#         self.stdout.write(f"Projet       : {project.nom}")
#         self.stdout.write(f"Programme    : {program.name}")
#         self.stdout.write(f"Dataset      : {dataset.name}")
#         self.stdout.write(f"Îlots créés  : {created_blocks}")
#         self.stdout.write(f"Parcelles créées : {created_parcels}")
#         self.stdout.write(f"Parcelles mises à jour : {updated_parcels}")
#         self.stdout.write(f"Géométries vides ignorées : {skipped_empty_geometry}")

# /Users/ogahserge/Documents/parcelaireKG/parcelaire/management/commands/import_parcellaire_geojson.py
import json
import os
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry
from django.db import transaction
from django.utils.text import slugify

from parcelaire.models import (
    Country,
    Place,
    ProjetImmobilier,
    RealEstateProgram,
    ProgramPhase,
    ParcelDataset,
    ProgramBlock,
    Parcel,
)


def strip_z_coordinates(coords):
    """
    Supprime la 3e dimension (Z) d'une structure GeoJSON coordinates.
    Compatible Point, LineString, Polygon, MultiPolygon, etc.
    """
    if isinstance(coords, (list, tuple)):
        if not coords:
            return coords

        # Cas d'un point : [x, y] ou [x, y, z]
        if isinstance(coords[0], (int, float)):
            return list(coords[:2])

        # Cas imbriqué
        return [strip_z_coordinates(item) for item in coords]

    return coords


def make_2d_geojson_geometry(geometry):
    """
    Retourne une géométrie GeoJSON 2D propre.
    """
    if not geometry or not geometry.get("type") or "coordinates" not in geometry:
        return None

    return {
        "type": geometry["type"],
        "coordinates": strip_z_coordinates(geometry["coordinates"]),
    }


def to_decimal(value):
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = "Importe un fichier GeoJSON parcellaire dans la base"

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Chemin du fichier GeoJSON")
        parser.add_argument("--country", type=str, required=True, help="Nom du pays")
        parser.add_argument("--project-code", type=str, required=True, help="Code du projet immobilier")
        parser.add_argument("--project-name", type=str, required=True, help="Nom du projet immobilier")
        parser.add_argument("--program-code", type=str, required=True, help="Code du programme immobilier")
        parser.add_argument("--program-name", type=str, required=True, help="Nom du programme immobilier")
        parser.add_argument("--phase-code", type=str, help="Code de la phase")
        parser.add_argument("--phase-name", type=str, help="Nom de la phase")
        parser.add_argument("--place-id", type=int, help="ID du lieu Place")
        parser.add_argument("--dataset-name", type=str, help="Nom du dataset")
        parser.add_argument("--replace", action="store_true", help="Supprime les parcelles du dataset courant avant import")

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options["file"]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                geojson = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Fichier introuvable : {file_path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}")

        if geojson.get("type") != "FeatureCollection":
            raise CommandError("Le fichier doit être un GeoJSON de type FeatureCollection.")

        country_name = options["country"]
        project_code = options["project_code"]
        project_name = options["project_name"]
        program_code = options["program_code"]
        program_name = options["program_name"]
        phase_code = options.get("phase_code")
        phase_name = options.get("phase_name")
        place_id = options.get("place_id")

        dataset_name = options.get("dataset_name") or geojson.get("name") or "Import parcellaire"

        country, _ = Country.objects.get_or_create(nom=country_name)

        place = None
        if place_id:
            try:
                place = Place.objects.get(pk=place_id)
            except Place.DoesNotExist:
                raise CommandError(f"Aucun Place trouvé avec l'id={place_id}")

            if place.country_id != country.id:
                raise CommandError("Le Place fourni n'appartient pas au pays sélectionné.")

        project, _ = ProjetImmobilier.objects.get_or_create(
            code=project_code,
            defaults={
                "nom": project_name,
                "slug": slugify(project_name),
                "country": country,
                "place": place,
            }
        )

        updated_project = False
        if project.nom != project_name:
            project.nom = project_name
            updated_project = True
        if not project.slug:
            project.slug = slugify(project_name)
            updated_project = True
        if project.country_id != country.id:
            project.country = country
            updated_project = True
        if place and project.place_id != place.id:
            project.place = place
            updated_project = True
        if updated_project:
            project.save()

        program, _ = RealEstateProgram.objects.get_or_create(
            code=program_code,
            defaults={
                "name": program_name,
                "slug": slugify(program_name),
                "country": country,
                "place": place,
                "project": project,
            }
        )

        updated_program = False
        if program.name != program_name:
            program.name = program_name
            updated_program = True
        if not program.slug:
            program.slug = slugify(program_name)
            updated_program = True
        if program.country_id != country.id:
            program.country = country
            updated_program = True
        if place and program.place_id != place.id:
            program.place = place
            updated_program = True
        if program.project_id != project.id:
            program.project = project
            updated_program = True
        if updated_program:
            program.save()

        phase = None
        if phase_code and phase_name:
            phase, _ = ProgramPhase.objects.get_or_create(
                program=program,
                code=phase_code,
                defaults={
                    "name": phase_name,
                    "order": 1,
                }
            )
            if phase.name != phase_name:
                phase.name = phase_name
                phase.save()

        dataset, created = ParcelDataset.objects.get_or_create(
            program=program,
            phase=phase,
            name=dataset_name,
            defaults={
                "source_code": geojson.get("name"),
                "source_file_name": os.path.basename(file_path),
                "geojson_type": geojson.get("type", "FeatureCollection"),
                "crs_name": ((geojson.get("crs") or {}).get("properties") or {}).get("name"),
                "xy_coordinate_resolution": geojson.get("xy_coordinate_resolution"),
                "version": "1.0",
                "is_current": True,
            }
        )

        if not created:
            dataset.source_code = geojson.get("name")
            dataset.source_file_name = os.path.basename(file_path)
            dataset.geojson_type = geojson.get("type", "FeatureCollection")
            dataset.crs_name = ((geojson.get("crs") or {}).get("properties") or {}).get("name")
            dataset.xy_coordinate_resolution = geojson.get("xy_coordinate_resolution")
            dataset.save()

        if options["replace"]:
            deleted_count, _ = Parcel.objects.filter(dataset=dataset).delete()
            self.stdout.write(self.style.WARNING(f"{deleted_count} parcelle(s) supprimée(s) avant réimport."))

        features = geojson.get("features", [])
        if not features:
            raise CommandError("Aucune feature trouvée dans le GeoJSON.")

        blocks_cache = {}
        created_blocks = 0
        created_parcels = 0
        updated_parcels = 0
        skipped_empty_geometry = 0
        invalid_geometry_count = 0

        for feature in features:
            properties = feature.get("properties", {}) or {}
            geometry = feature.get("geometry", {}) or {}

            fid = properties.get("fid")
            lot_number = properties.get("LOT_NOM")
            ilot_code = properties.get("ILOT_NOM")
            area = properties.get("Area")

            block = None
            if ilot_code:
                if ilot_code not in blocks_cache:
                    block, block_created = ProgramBlock.objects.get_or_create(
                        program=program,
                        code=str(ilot_code),
                        defaults={
                            "label": f"Îlot {ilot_code}",
                            "phase": phase,
                        }
                    )
                    if not block_created:
                        updated = False
                        if phase and block.phase_id != phase.id:
                            block.phase = phase
                            updated = True
                        if not block.label:
                            block.label = f"Îlot {ilot_code}"
                            updated = True
                        if updated:
                            block.save()
                    else:
                        created_blocks += 1

                    blocks_cache[ilot_code] = block

                block = blocks_cache[ilot_code]

            geom_obj = None
            centroid = None

            clean_geometry = make_2d_geojson_geometry(geometry)
            if clean_geometry:
                try:
                    geom_obj = GEOSGeometry(json.dumps(clean_geometry), srid=4326)
                    if geom_obj and not geom_obj.empty:
                        centroid = geom_obj.centroid
                except Exception as e:
                    invalid_geometry_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"Feature fid={fid}: géométrie invalide ignorée ({e})")
                    )
            else:
                skipped_empty_geometry += 1

            parcel_code = None
            if ilot_code is not None and lot_number is not None:
                parcel_code = f"{ilot_code}-{lot_number}"

            defaults = {
                "program": program,
                "phase": phase,
                "block": block,
                "source_fid": fid,
                "lot_number": str(lot_number) if lot_number is not None else None,
                "parcel_code": parcel_code,
                "official_area_m2": to_decimal(area),
                "computed_area_m2": to_decimal(area),
                "geometry": geom_obj,
                "centroid": centroid,
                "geometry_valid": bool(geom_obj and not geom_obj.empty),
                "has_number": lot_number is not None,
                "duplicate_flag": False,
                "metadata": {
                    "source_properties": properties,
                },
            }

            parcel_qs = Parcel.objects.filter(dataset=dataset, source_fid=fid)
            if parcel_qs.exists():
                parcel = parcel_qs.first()
                for field, value in defaults.items():
                    setattr(parcel, field, value)
                parcel.save()
                updated_parcels += 1
            else:
                Parcel.objects.create(dataset=dataset, **defaults)
                created_parcels += 1

        program.estimated_lot_count = Parcel.objects.filter(program=program).count()

        total_area_values = list(
            Parcel.objects.filter(program=program)
            .exclude(official_area_m2__isnull=True)
            .values_list("official_area_m2", flat=True)
        )
        program.total_area_m2 = sum(total_area_values, Decimal("0"))
        program.save()

        self.stdout.write(self.style.SUCCESS("Import terminé avec succès."))
        self.stdout.write(f"Projet                    : {project.nom}")
        self.stdout.write(f"Programme                 : {program.name}")
        self.stdout.write(f"Dataset                   : {dataset.name}")
        self.stdout.write(f"Îlots créés               : {created_blocks}")
        self.stdout.write(f"Parcelles créées          : {created_parcels}")
        self.stdout.write(f"Parcelles mises à jour    : {updated_parcels}")
        self.stdout.write(f"Géométries vides ignorées : {skipped_empty_geometry}")
        self.stdout.write(f"Géométries invalides      : {invalid_geometry_count}")