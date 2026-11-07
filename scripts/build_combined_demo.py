import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.media_probe import find_tool, get_video_info

def build_combined_demo():
    vids = [
        "01_inspector_panel.mp4",
        "02_preview_volume.mp4",
        "03_inspector_mousewheel.mp4",
        "04_intro_y_offsets.mp4",
        "05_watermark_export.mp4",
        "06_manual_column_distribution.mp4"
    ]

    proof_dir = Path("final_delivery_proof").resolve()
    concat_list = proof_dir / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for v in vids:
            p = (proof_dir / v).as_posix()
            f.write(f"file '{p}'\n")

    ffmpeg = find_tool("ffmpeg")
    out_combined = proof_dir / "final_combined_demo.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_combined)
    ]
    subprocess.run(cmd, check=True)
    if concat_list.is_file():
        concat_list.unlink()

    info = get_video_info(str(out_combined))
    print(f"Combined demo video created successfully at {out_combined}!")
    print(f"Video info: {info}, Size: {out_combined.stat().st_size} bytes")

if __name__ == "__main__":
    build_combined_demo()
