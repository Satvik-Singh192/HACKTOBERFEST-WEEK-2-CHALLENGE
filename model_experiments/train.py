from ultralytics import YOLO

# Load the lightweight nano model
model = YOLO('yolo11n.pt')

# Train the model on your dataset
results = model.train(
    data='./im_data/data.yaml',
    epochs=50,
    imgsz=352,
    device='cpu'  # Change to '0' if you have a dedicated NVIDIA GPU
)
