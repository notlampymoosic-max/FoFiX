"""
Sng.py - Support for Clone Hero / YARG .sng binary song packages in FoFiX.
"""
import os
import re
import sys
from pathlib import Path
import Log

try:
  from sng_parser.decode import decode_sng
  SNG_AVAILABLE = True
except Exception as e:
  SNG_AVAILABLE = False
  Log.warn(f"sng_parser could not be imported: {e}")

def is_sng_file(path):
  """Check if a file exists and begins with the SNGPKG magic header."""
  if not path or not os.path.isfile(path):
    return False
  try:
    with open(path, "rb") as f:
      return f.read(6) == b"SNGPKG"
  except Exception:
    return False

def clean_song_dirname(sng_filename):
  """Generate a clean directory name from an .sng filename."""
  base = os.path.basename(sng_filename)
  if base.lower().endswith(".sng"):
    base = base[:-4]
  # Sanitize illegal directory characters
  base = re.sub(r'[\\/*?:"<>|]', "", base).strip()
  return base or "SNG_Song"

def unpack_sng(sng_path, target_parent_dir, folder_name=None, overwrite=False):
  """
  Unpack an .sng package into target_parent_dir / folder_name.
  Returns the absolute path to the unpacked directory, or None on failure.
  """
  if not SNG_AVAILABLE:
    Log.warn("SNG extraction requested but sng_parser is unavailable.")
    return None

  if not is_sng_file(sng_path):
    return None

  if folder_name is None:
    folder_name = clean_song_dirname(sng_path)

  dest_dir = os.path.join(target_parent_dir, folder_name)

  # Check if already extracted with song.ini
  if not overwrite and os.path.isdir(dest_dir):
    if os.path.isfile(os.path.join(dest_dir, "song.ini")):
      return dest_dir

  try:
    os.makedirs(dest_dir, exist_ok=True)
    decode_sng(
      Path(sng_path),
      outdir=Path(target_parent_dir),
      sng_dir=folder_name,
      allow_nonsng_files=True,
      overwrite=True,
    )
    Log.notice(f"Successfully unpacked .sng package: {os.path.basename(sng_path)} -> {folder_name}")
    return dest_dir
  except Exception as e:
    Log.error(f"Failed to unpack .sng file {sng_path}: {e}")
    return None

def scan_and_unpack_sngs(directory):
  """
  Scan a directory for .sng files and unpack each into its own subfolder if not already unpacked.
  Returns a list of unpacked directory names (relative to directory).
  """
  if not os.path.isdir(directory):
    return []

  unpacked = []
  try:
    entries = os.listdir(directory)
  except Exception:
    return []

  for entry in entries:
    if not entry.lower().endswith(".sng"):
      continue
    sng_path = os.path.join(directory, entry)
    if not os.path.isfile(sng_path):
      continue

    dirname = clean_song_dirname(entry)
    dest_path = os.path.join(directory, dirname)

    # Check if already unpacked
    if os.path.isdir(dest_path) and os.path.isfile(os.path.join(dest_path, "song.ini")):
      unpacked.append(dirname)
      continue

    # Unpack
    result = unpack_sng(sng_path, directory, folder_name=dirname)
    if result:
      unpacked.append(dirname)

  return unpacked
