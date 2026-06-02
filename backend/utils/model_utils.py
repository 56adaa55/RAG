import os
import logging

# Configure logger
logger = logging.getLogger(__name__)

def get_huggingface_model_path(model_name: str) -> str:
    """
    Convert a model name to a local path if the model exists locally.
    
    Args:
        model_name: The name of the model (e.g. "sentence-transformers/all-MiniLM-L6-v2")
        
    Returns:
        str: The local path to the model if it exists, otherwise returns the original model name
    """
    model_path = os.environ.get("HF_MODEL_PATH")
    if not model_path or not os.path.exists(model_path):
        logger.info(f"Using remote model: {model_name}")
        return model_name

    local_model_name = os.path.join(model_path, *model_name.split("/"))
    if os.path.exists(local_model_name):
        logger.info(f"Using local model: {local_model_name}")
        return local_model_name

    logger.info(f"Using remote model: {model_name}")
    return model_name 