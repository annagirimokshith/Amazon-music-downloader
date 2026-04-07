
import os
import re
import json
import shutil
import requests
import subprocess


class AmazonMusicDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

    def extract_asin(self, amazon_url: str) -> str:
        match = re.search(r'(B[0-9A-Z]{9})', amazon_url)
        if not match:
            raise Exception(f"Failed to extract ASIN from URL: {amazon_url}")
        return match.group(1)

    def detect_codec(self, file_path):
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("ffprobe failed")
        data = json.loads(result.stdout)
        return data["streams"][0]["codec_name"]

    def download_from_afkar(self, amazon_url, output_dir="."):
        asin = self.extract_asin(amazon_url)
        api_url = f"https://amzn.afkarxyz.qzz.io/api/track/{asin}"
        print(f"Fetching API for ASIN: {asin}")

        r = self.session.get(api_url)
        if r.status_code != 200:
            raise Exception(f"API error: {r.status_code}")

        data = r.json()
        stream_url = data.get("streamUrl")
        key = data.get("decryptionKey")

        if not stream_url:
            raise Exception("No stream URL found")

        os.makedirs(output_dir, exist_ok=True)
        temp_file = os.path.join(output_dir, f"{asin}_enc.m4a")

        print("Downloading encrypted file...")
        with self.session.get(stream_url, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, "wb") as f:
                shutil.copyfileobj(r.raw, f)

        print("Download complete")

        if not key:
            return temp_file

        print("Detecting codec...")
        codec = self.detect_codec(temp_file)
        print(f"Codec detected: {codec}")

        if codec == "flac":
            final_file = os.path.join(output_dir, f"{asin}.flac")
        elif codec in ["aac", "alac"]:
            final_file = os.path.join(output_dir, f"{asin}.m4a")
        else:
            final_file = os.path.join(output_dir, f"{asin}.{codec}")

        print("Decrypting with ffmpeg...")
        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-decryption_key", key.strip(),
            "-i", temp_file,
            "-c", "copy",
            "-y",
            final_file
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            print(result.stderr.decode())
            raise Exception("FFmpeg decryption failed")

        if os.path.exists(temp_file):
            os.remove(temp_file)

        if not os.path.exists(final_file) or os.path.getsize(final_file) == 0:
            raise Exception("Output file invalid")

        print(f"Done: {final_file}")
        return final_file


if __name__ == "__main__":
    downloader = AmazonMusicDownloader()
    amazon_url = "https://music.amazon.in/albums/B0GVPPY2HB"

    try:
        path = downloader.download_from_afkar(amazon_url, "./downloads")
        print("Saved to:", path)
    except Exception as e:
        print("Error:", str(e))
