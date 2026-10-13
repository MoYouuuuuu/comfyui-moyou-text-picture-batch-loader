from .text_loader import Moyou_Text_Batch_Loader
from .image_loader import Moyou_Image_Batch_Loader

NODE_CLASS_MAPPINGS = {
    "Moyou Text Batch Loader": Moyou_Text_Batch_Loader,
    "Moyou Image Batch Loader": Moyou_Image_Batch_Loader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Moyou Text Batch Loader": "Moyou Text Batch Loader",
    "Moyou Image Batch Loader": "moyou Load Image Batch"
}
