import os
import subprocess


class FFmpegService:
    @staticmethod
    def concat_videos(video_paths: list[str], output_path: str) -> str:
        list_file = f"{output_path}.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for path in video_paths:
                f.write(f"file '{os.path.abspath(path)}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path,
        ]
        subprocess.run(cmd, check=True)
        return output_path