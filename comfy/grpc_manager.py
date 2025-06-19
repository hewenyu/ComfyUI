import grpc
import atexit
import logging
import threading
from comfy import cli_args
from comfy.instance_manager import get_comfyui_id
from comfy.generated import status_notifier_pb2
from comfy.generated import status_notifier_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
class GrpcManager:
    _instance = None
    _lock = threading.Lock()
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(GrpcManager, cls).__new__(cls)
        return cls._instance
    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.stub = None
        self.comfyui_id = None
        
        if cli_args.args.grpc_endpoint:
            self.comfyui_id = get_comfyui_id()
            try:
                if cli_args.args.grpc_secure:
                    credentials = grpc.ssl_channel_credentials()
                    channel = grpc.secure_channel(cli_args.args.grpc_endpoint, credentials)
                else:
                    channel = grpc.insecure_channel(cli_args.args.grpc_endpoint)
                
                self.stub = status_notifier_pb2_grpc.StatusNotifierStub(channel)
                logging.info(f"gRPC client initialized for endpoint: {cli_args.args.grpc_endpoint}")
                
                # Register shutdown hook
                atexit.register(self.notify_shutdown)
                
            except Exception as e:
                logging.error(f"Failed to initialize gRPC client: {e}")
                self.stub = None
        
        self._initialized = True
    def publish(self, status_update):
        if not self.stub:
            return
            
        # Add common information
        status_update.comfyui_id = self.comfyui_id
        status_update.timestamp.GetCurrentTime()
        try:
            reply = self.stub.SendStatus(status_update)
            if not reply.acknowledged:
                logging.warning("gRPC server did not acknowledge the status update.")
        except grpc.RpcError as e:
            logging.error(f"gRPC error while sending status: {e.code()} - {e.details()}")
    def notify_startup(self):
        if not self.stub:
            return
            
        logging.info("Sending INSTANCE_START event...")
        # Placeholder for version
        version = "1.0.0" 
        
        status_update = status_notifier_pb2.StatusUpdate(
            event=status_notifier_pb2.INSTANCE_START,
            instance_info=status_notifier_pb2.InstanceInfo(version=version)
        )
        self.publish(status_update)
    def notify_shutdown(self):
        if not self.stub:
            return
            
        logging.info("Sending INSTANCE_SHUTDOWN event...")
        status_update = status_notifier_pb2.StatusUpdate(
            event=status_notifier_pb2.INSTANCE_SHUTDOWN
        )
        # Use a temporary stub for shutdown as the main one might be closing
        try:
            with grpc.insecure_channel(cli_args.args.grpc_endpoint) as channel:
                stub = status_notifier_pb2_grpc.StatusNotifierStub(channel)
                stub.SendStatus(status_update, timeout=5) # 5-second timeout
        except grpc.RpcError as e:
            logging.error(f"gRPC error during shutdown notification: {e}")
# Global instance
grpc_manager = GrpcManager() 