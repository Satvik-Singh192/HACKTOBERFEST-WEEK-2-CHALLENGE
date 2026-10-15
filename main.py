from pathlib import Path

from preprocess import config
from preprocess.pipeline import VideoFileSource, run_pipeline
from model_experiments.pipeline import KillfeedPipeline
from backend.event_pipeline import EventPipeline



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
    event_pipeline = EventPipeline()


    def handle_candidate(candidate) -> None:
        event = ml_pipeline.process(candidate.crop_bgr)

        if event is None:
            return

        event_pipeline.process_event(event)

        print(
            f"Attacker: {event.attacker} | "
            f"Icons: {event.icons} | "
            f"Victim: {event.victim}"
        )

    run_pipeline(
        source=source,
        on_candidate=handle_candidate,
    )


if __name__ == "__main__":
    main()
