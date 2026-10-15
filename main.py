from pathlib import Path

from preprocess import config
from preprocess.pipeline import VideoFileSource, run_pipeline
from model_experiments.pipeline import KillfeedPipeline


# Update this to the actual location of your model weights.
YOLO_WEIGHTS = Path(
    "./best_openvino_model/"
)


def main() -> None:
    source = VideoFileSource(
        video_path=config.VIDEO_PATH,
        duration_seconds=config.DURATION_SECONDS,
    )

    # Load OCR and YOLO once, not once per candidate.
    ml_pipeline = KillfeedPipeline(
        yolo_weights_path=str(YOLO_WEIGHTS),
        min_ocr_conf=0.50,
        yolo_conf=0.25,
        imgsz=352,
    )

    def handle_candidate(candidate) -> None:
        result = ml_pipeline.process(candidate.crop_bgr)

        if result is None:
            print(
                f"[ML REJECTED] "
                f"t={candidate.timestamp_seconds:.2f}s "
                f"frame={candidate.frame_index}"
            )
            return

        print(
            f"[KILL FEED EVENT] "
            f"t={candidate.timestamp_seconds:.2f}s "
            f"frame={candidate.frame_index} | "
            f"{result['attacker']} "
            f"-- {result['icon']} --> "
            f"{result['victim']}"
        )

    run_pipeline(
        source=source,
        on_candidate=handle_candidate,
    )


if __name__ == "__main__":
    main()
