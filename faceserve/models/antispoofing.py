from typing import Any, List
import cv2
import numpy as np
import onnxruntime as ort

from faceserve.utils import crop_image, align_5_points
from .interface import InterfaceModel

sess_options = ort.SessionOptions()
sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL


class SpoofingNet(InterfaceModel):
    """SpoofingNet"""

    def __init__(self, model_path) -> None:
        self.model = self.load_model(model_path)
        self.input_name = self.model.get_inputs()[0].name
        self.output_name = self.model.get_outputs()[0].name
        _, h, w, _ = self.model.get_inputs()[0].shape
        self.model_input_size = (w, h)

    def load_model(self, path: str) -> ort.InferenceSession:
        return ort.InferenceSession(
            path,
            sess_options=sess_options,
            providers=[
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ],
        )

    def preprocess(self, image, xyxys, kpts):
        crops = []        
        # dets are of different sizes so batch preprocessing is not possible
        for box, kpt in zip(xyxys, kpts):
            x1, y1, _, _ = box
            crop = crop_image(image, box)
            # Align face
            # Scale the keypoints to the face size
            kpt[::3] = kpt[::3] - x1
            kpt[1::3] = kpt[1::3] - y1
            # Crop face
            crop = align_5_points(crop, kpt)
            crop = cv2.resize(crop, self.model_input_size)
            crop = (crop - 127.5) * 0.0078125
            crop = crop.transpose(2, 0, 1)
            crop = np.expand_dims(crop, axis=0)
            crops.append(crop)
        crops = np.concatenate(crops, axis=0)
        return crops

    def inference(self, image):
        if isinstance(image, list):
            image = np.array(image)
            
        result = self.model.run(
            [self.output_name], {self.input_name: image.astype("float32")}
        )[0]
        
        return result
    
    def postprocess(self, image: Any, **kwargs) -> Any:
        raise NotImplementedError

    def batch_inference(self, images: List[Any], **kwargs) -> List[Any]:
        raise NotImplementedError