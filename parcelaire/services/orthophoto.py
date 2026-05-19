"""
Service GDAL pour le pipeline orthophoto.

Encapsule tous les appels subprocess vers la suite GDAL (gdalwarp,
gdalinfo, gdaladdo, gdal_translate, gdal2tiles.py). Chaque méthode :

* est synchrone, idempotente sur ses fichiers de sortie
* journalise dans `OrthophotoProcessingLog` via le callback `logger`
* lève `OrthophotoProcessingError` en cas d'échec, avec stdout/stderr
  capturés pour faciliter le diagnostic
* ne touche PAS aux modèles Django (séparation responsabilités) — la
  tâche Celery orchestre, ce service exécute.

Tous les chemins manipulés sont des `pathlib.Path` absolus.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =====================================================================
# Exceptions & types
# =====================================================================


class OrthophotoProcessingError(RuntimeError):
    """Erreur du pipeline GDAL (capture stdout/stderr de la commande)."""

    def __init__(self, message: str, *, command: str = "", stdout: str = "", stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class GdalInfo:
    """Métadonnées extraites de `gdalinfo -json`."""

    srs: str = ""
    width: int = 0
    height: int = 0
    band_count: int = 0
    color_interps: List[str] = field(default_factory=list)
    bounds: Optional[Tuple[float, float, float, float]] = None  # (minx, miny, maxx, maxy) WGS84
    raw: dict = field(default_factory=dict)

    @property
    def has_palette(self) -> bool:
        return any(ci.lower() == "palette" for ci in self.color_interps)

    @property
    def is_rgba(self) -> bool:
        wanted = {"red", "green", "blue", "alpha"}
        return {ci.lower() for ci in self.color_interps[:4]}.issuperset(wanted)


# =====================================================================
# Helper de logging
# =====================================================================

LogFn = Callable[[str, str, Optional[str]], None]
"""Signature : log(level, message, command=None). Permet à la task Celery
de brancher l'écriture dans OrthophotoProcessingLog."""


def _noop_log(level: str, message: str, command: Optional[str] = None) -> None:
    logger.info("[orthophoto] %s — %s", level, message)


# =====================================================================
# Wrapper subprocess
# =====================================================================


def _run(
    cmd: List[str],
    *,
    log: LogFn = _noop_log,
    step: str = "",
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> Tuple[str, str]:
    """
    Exécute `cmd` et renvoie (stdout, stderr).

    - Sortie complète capturée (pas streamée) → simple à logger
    - Lève `OrthophotoProcessingError` en cas de returncode != 0
    - Le `step` est utilisé comme préfixe de log (ex. "Reprojection")
    """
    pretty = " ".join(_quote_arg(a) for a in cmd)
    log("INFO", f"{step or 'GDAL'} — exécution", pretty)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OrthophotoProcessingError(
            f"Commande introuvable : {cmd[0]} ({exc}). GDAL installé ?",
            command=pretty,
        ) from exc

    if result.returncode != 0:
        msg = (
            f"{step or 'GDAL'} — échec (code {result.returncode})\n"
            f"stderr: {result.stderr.strip()[:2000]}"
        )
        log("ERROR", msg, pretty)
        raise OrthophotoProcessingError(
            msg,
            command=pretty,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    # On ne logge le stdout que si pertinent (gdalinfo) ou via WARNING.
    if result.stderr:
        # Les outils GDAL écrivent souvent leur progression sur stderr ;
        # on n'enregistre qu'une note "warning" pour ne pas polluer.
        log("WARNING", f"{step or 'GDAL'} — sortie d'erreur capturée", result.stderr[:1500])
    return result.stdout, result.stderr


def _quote_arg(arg: str) -> str:
    if not arg or any(c in arg for c in " \t\"'$&|;()<>"):
        return '"' + arg.replace('"', '\\"') + '"'
    return arg


# =====================================================================
# Pipeline GDAL
# =====================================================================


class OrthophotoPipeline:
    """
    Pipeline complet (reproject → overviews → tiles XYZ).

    Usage typique (dans la tâche Celery) :

        with OrthophotoPipeline(work_dir, tiles_dir, log=log).run(
            source=Path('/media/upload.tif'),
            min_zoom=15,
            max_zoom=22,
            target_srs='EPSG:3857',
        ) as result:
            ortho.processed_file.name = result.processed_rel_path
            ortho.bounds = result.bounds_geos
    """

    def __init__(
        self,
        work_dir: Path,
        tiles_dir: Path,
        *,
        log: LogFn = _noop_log,
        gdal_processes: int = 8,
    ):
        self.work_dir = Path(work_dir)
        self.tiles_dir = Path(tiles_dir)
        self.log = log
        self.gdal_processes = max(1, int(gdal_processes))

        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.tiles_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Étape 2 — reprojection EPSG:3857
    # -----------------------------------------------------------------
    def reproject_to_3857(self, source: Path, target: Path) -> Path:
        cmd = [
            "gdalwarp",
            "-overwrite",
            "-t_srs", "EPSG:3857",
            "-r", "bilinear",
            "-multi",
            "-wo", "NUM_THREADS=ALL_CPUS",
            "-co", "TILED=YES",
            "-co", "COMPRESS=DEFLATE",
            "-co", "BIGTIFF=YES",
            str(source),
            str(target),
        ]
        _run(cmd, log=self.log, step="Reprojection EPSG:3857")
        if not target.exists():
            raise OrthophotoProcessingError(
                "gdalwarp s'est terminé sans erreur mais le fichier de sortie est introuvable.",
                command=" ".join(cmd),
            )
        return target

    # -----------------------------------------------------------------
    # Étape 3 — lecture gdalinfo JSON
    # -----------------------------------------------------------------
    def inspect(self, path: Path) -> GdalInfo:
        stdout, _ = _run(
            ["gdalinfo", "-json", "-stats", str(path)],
            log=self.log,
            step="Lecture gdalinfo",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise OrthophotoProcessingError(
                f"gdalinfo n'a pas produit un JSON valide : {exc}",
                command="gdalinfo -json",
                stdout=stdout[:1000],
            ) from exc

        info = GdalInfo(
            srs=(data.get("coordinateSystem") or {}).get("wkt", ""),
            width=int(data.get("size", [0, 0])[0]),
            height=int(data.get("size", [0, 0])[1]),
            band_count=len(data.get("bands") or []),
            color_interps=[b.get("colorInterpretation", "") for b in (data.get("bands") or [])],
            raw=data,
        )

        # Bounds WGS84 : `wgs84Extent` est un GeoJSON Polygon.
        wgs84 = data.get("wgs84Extent") or {}
        coords = wgs84.get("coordinates") or []
        if coords and coords[0]:
            xs = [pt[0] for pt in coords[0]]
            ys = [pt[1] for pt in coords[0]]
            info.bounds = (min(xs), min(ys), max(xs), max(ys))

        self.log(
            "INFO",
            f"Source : {info.width}×{info.height}px, {info.band_count} bande(s), "
            f"ColorInterp={','.join(info.color_interps) or '?'}",
            None,
        )
        return info

    # -----------------------------------------------------------------
    # Étape 4 — overviews
    # -----------------------------------------------------------------
    def build_overviews(self, path: Path, levels: Iterable[int] = (2, 4, 8, 16, 32)) -> None:
        cmd = ["gdaladdo", "-r", "average", str(path), *[str(l) for l in levels]]
        _run(cmd, log=self.log, step="Génération des overviews")

    # -----------------------------------------------------------------
    # Étape 5 — VRT RGBA si palette
    # -----------------------------------------------------------------
    def expand_palette_to_rgba(self, source: Path, vrt_out: Path) -> Path:
        cmd = [
            "gdal_translate",
            "-of", "VRT",
            "-expand", "rgba",
            str(source),
            str(vrt_out),
        ]
        _run(cmd, log=self.log, step="Expansion palette → RGBA (VRT)")
        return vrt_out

    # -----------------------------------------------------------------
    # Étape 6 — tuiles XYZ
    # -----------------------------------------------------------------
    def generate_tiles(
        self,
        source: Path,
        out_dir: Path,
        *,
        min_zoom: int,
        max_zoom: int,
    ) -> Path:
        if min_zoom > max_zoom:
            raise OrthophotoProcessingError(
                f"min_zoom ({min_zoom}) > max_zoom ({max_zoom})",
            )
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "gdal2tiles.py",
            "--xyz",
            f"--processes={self.gdal_processes}",
            "--tiledriver=PNG",
            "-z", f"{min_zoom}-{max_zoom}",
            str(source),
            str(out_dir),
        ]
        _run(cmd, log=self.log, step="Génération des tuiles XYZ")
        return out_dir

    # -----------------------------------------------------------------
    # Nettoyage : supprime les tuiles existantes (avant relance)
    # -----------------------------------------------------------------
    def purge_tiles(self) -> None:
        if self.tiles_dir.exists():
            shutil.rmtree(self.tiles_dir)
            self.log("INFO", f"Tuiles supprimées : {self.tiles_dir}", None)
        self.tiles_dir.mkdir(parents=True, exist_ok=True)


# =====================================================================
# Helpers de chemins
# =====================================================================


def build_paths(program_slug: str, year: int, month: int, *, media_root: Path) -> dict:
    """
    Construit la triplette de chemins (work_dir, tiles_dir, tiles_url) pour
    une orthophoto donnée — utilisé par la tâche Celery et par l'API map.
    """
    media_root = Path(media_root)
    sub = f"{program_slug}/{year}/{month:02d}"
    work_dir = media_root / "orthophotos" / "processed" / sub
    tiles_dir = media_root / "tiles_ortho" / sub
    tiles_url = f"/media/tiles_ortho/{sub}/{{z}}/{{x}}/{{y}}.png"
    return {
        "work_dir": work_dir,
        "tiles_dir": tiles_dir,
        "tiles_url": tiles_url,
        "subpath": sub,
    }
