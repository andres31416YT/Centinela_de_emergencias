import os
import torch
import numpy as np
import cv2
from torchvision import transforms
from torch import nn

MODEL_PATH = os.getenv("MODEL_PATH", "ML/models/resnet50/optimal/best_model.pt")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FIRE_CONFIDENCE_THRESHOLD = float(os.getenv("FIRE_CONFIDENCE_THRESHOLD", "0.75"))

preprocess = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

CLASS_NAMES = ["Fire", "Normal", "Smoke"]

_model = None

def _try_match_resnet_keys(state_dict):
    if "fc.weight" in state_dict:
        return "resnet50", 3
    for k in state_dict.keys():
        if k.startswith("layer"):
            return "resnet50", 3
    return None, None

def _build_resnet50(num_classes=3):
    from torchvision import models
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(2048, num_classes)
    return model

def _build_any_resnet(state_dict, num_classes=3):
    model = _build_resnet50(num_classes)
    model_keys = set(model.state_dict().keys())
    extra = set(state_dict.keys()) - model_keys
    if extra and "fc" in " ".join(extra):
        model.fc = nn.Sequential()
        layers = []
        # Order by posicion en el state dict si es posible
        keys = list(state_dict.keys())
        # Heurística: si hay fc.1, fc.4, fc.7 ... usar Sequential directo
        # Si no, reconstruir simples linear/dropout/bn segun nombres
        for k in keys:
            if k.startswith("fc.") and k.endswith(".weight"):
                prefix = k.split(".")[1]
                suffix = k.replace(f"fc.{prefix}.", "")
                if suffix == "weight":
                    out = state_dict[k].shape[0]
                    inp = state_dict[k].shape[1] if k.replace("weight", "bias") in state_dict else state_dict[k].shape[1]
                    layers.append(nn.Linear(inp, out))
                elif suffix == "bias":
                    pass
        # Fallback: si hay fc.1/fc.4 es probablemente una Sequential custom
        if "fc.1.weight" in state_dict and "fc.4.weight" in state_dict:
            model.fc = nn.Sequential(
                nn.Linear(2048, 512),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(512, num_classes),
            )
        else:
            model.fc = nn.Linear(2048, num_classes)
    return model

def load_model():
    global _model
    if _model is not None:
        return _model

    loaded = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)

    if isinstance(loaded, nn.Module):
        _model = loaded.to(DEVICE)
    else:
        if not isinstance(loaded, dict):
            loaded = loaded.state_dict() if hasattr(loaded, "state_dict") else loaded
        state_dict = loaded
        head_name, num_classes = _try_match_resnet_keys(state_dict)
        model = _build_resnet50(num_classes or 3)
        model.load_state_dict(state_dict, strict=False)
        _model = model.to(DEVICE)

    _model.eval()
    return _model

@torch.no_grad()
def predict_frame(model, frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    input_tensor = preprocess(rgb).unsqueeze(0).to(DEVICE)
    logits = model(input_tensor)
    probs = torch.nn.functional.softmax(logits, dim=1)[0]
    conf, idx = torch.max(probs, 0)
    predicted_class = CLASS_NAMES[idx.item()]

    if conf.item() < FIRE_CONFIDENCE_THRESHOLD:
        predicted_class = "Uncertain"

    return {
        "class": predicted_class,
        "confidence": round(conf.item(), 4),
        "all": {CLASS_NAMES[i]: round(probs[i].item(), 4) for i in range(len(CLASS_NAMES))}
    }
