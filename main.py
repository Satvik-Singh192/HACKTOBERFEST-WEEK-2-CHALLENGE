"""Run the BGMI kill-feed pipeline from the project root."""

from preprocess import config
from preprocess.pipeline import VideoFileSource, run_pipeline


def main() -> None:
    # The MP4 emits frames sequentially through the same interface that an
    # eventual OBS source will implement. The processing pipeline doesn't need
    # to know whether each frame came from a file or a live stream.
    source = VideoFileSource(
        video_path=config.VIDEO_PATH,
        duration_seconds=config.DURATION_SECONDS,
    )
    run_pipeline(source)


if __name__ == "__main__":
    main()
