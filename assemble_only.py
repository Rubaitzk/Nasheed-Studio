"""Run phases 4-6 of build_release.py on the existing bundle (no rebuild)."""
import sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Import build_release internals
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("build_release",
    str(pathlib.Path(__file__).parent / "build_release.py"))
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)

bundle = br.DIST_DIR / br.BUNDLE_NAME
print(f"Bundle: {bundle}")
print(f"EXE: {bundle / (br.BUNDLE_NAME + '.exe')}")
print(f"EXE exists: {(bundle / (br.BUNDLE_NAME + '.exe')).exists()}")

br.verify_bundle(bundle)
release_dir = br.assemble_release(bundle)
br.write_manifest(bundle, release_dir)

print(f"\nRelease assembled at: {release_dir}")
print(f"ZIP: {release_dir / br.ZIP_NAME}")
