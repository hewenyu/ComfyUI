import uuid
import os
class InstanceManager:
    def __init__(self, base_directory=None):
        self.base_directory = base_directory if base_directory else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.instance_id_path = os.path.join(self.base_directory, ".comfyui_instance_id")
        self._comfyui_id = None
    def get_comfyui_id(self):
        if self._comfyui_id is None:
            if os.path.exists(self.instance_id_path):
                with open(self.instance_id_path, 'r') as f:
                    self._comfyui_id = f.read().strip()
            else:
                self._comfyui_id = str(uuid.uuid4())
                with open(self.instance_id_path, 'w') as f:
                    f.write(self._comfyui_id)
        return self._comfyui_id
# Global instance
instance_manager = InstanceManager()
get_comfyui_id = instance_manager.get_comfyui_id 