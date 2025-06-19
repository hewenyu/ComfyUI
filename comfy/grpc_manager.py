import grpc
import atexit
import logging
import threading
import time
from comfy import cli_args
from comfy.instance_manager import get_comfyui_id
from comfy.generated import status_notifier_pb2
from comfy.generated import status_notifier_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp

# 获取版本信息
try:
    import comfyui_version
    COMFYUI_VERSION = comfyui_version.__version__
except ImportError:
    COMFYUI_VERSION = "unknown"

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
        self.channel = None
        self.comfyui_id = None
        
        if cli_args.args.grpc_endpoint:
            self.comfyui_id = get_comfyui_id()
            try:
                if cli_args.args.grpc_secure:
                    credentials = grpc.ssl_channel_credentials()
                    self.channel = grpc.secure_channel(cli_args.args.grpc_endpoint, credentials)
                else:
                    self.channel = grpc.insecure_channel(cli_args.args.grpc_endpoint)
                
                self.stub = status_notifier_pb2_grpc.StatusNotifierStub(self.channel)
                logging.info(f"gRPC client initialized for endpoint: {cli_args.args.grpc_endpoint}")
                logging.info(f"ComfyUI instance ID: {self.comfyui_id}")
                
                # Register shutdown hook
                atexit.register(self.notify_shutdown)
                
            except Exception as e:
                logging.error(f"Failed to initialize gRPC client: {e}")
                self.stub = None
                self.channel = None
        
        self._initialized = True

    def _create_timestamp(self):
        """创建当前时间的Timestamp对象"""
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        return timestamp

    def publish(self, status_update):
        """发布状态更新，自动添加通用信息"""
        if not self.stub:
            logging.debug("gRPC stub not available, skipping publish")
            return
            
        # Add common information
        status_update.comfyui_id = self.comfyui_id
        if not status_update.HasField('timestamp'):
            status_update.timestamp.CopyFrom(self._create_timestamp())
        
        try:
            reply = self.stub.SendStatus(status_update, timeout=10)  # 10秒超时
            if reply.acknowledged:
                logging.debug(f"gRPC status sent successfully: {status_update.event}")
            else:
                logging.warning("gRPC server did not acknowledge the status update")
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                logging.warning("gRPC server unavailable")
            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                logging.warning("gRPC request timeout")
            else:
                logging.error(f"gRPC error while sending status: {e.code()} - {e.details()}")
        except Exception as e:
            logging.error(f"Unexpected error in gRPC publish: {e}")

    def notify_startup(self):
        """发送实例启动事件"""
        if not self.stub:
            logging.debug("gRPC stub not available, skipping startup notification")
            return
            
        logging.info(f"Sending INSTANCE_START event for ComfyUI {COMFYUI_VERSION}...")
        
        status_update = status_notifier_pb2.StatusUpdate(
            event=status_notifier_pb2.INSTANCE_START,
            instance_info=status_notifier_pb2.InstanceInfo(version=COMFYUI_VERSION)
        )
        self.publish(status_update)

    def notify_shutdown(self):
        """发送实例关闭事件"""
        if not self.stub:
            logging.debug("gRPC stub not available, skipping shutdown notification")
            return
            
        logging.info("Sending INSTANCE_SHUTDOWN event...")
        status_update = status_notifier_pb2.StatusUpdate(
            event=status_notifier_pb2.INSTANCE_SHUTDOWN
        )
        
        # 使用现有连接发送关闭消息
        try:
            if self.channel:
                stub = status_notifier_pb2_grpc.StatusNotifierStub(self.channel)
                status_update.comfyui_id = self.comfyui_id
                status_update.timestamp.CopyFrom(self._create_timestamp())
                stub.SendStatus(status_update, timeout=5)  # 5秒超时
                logging.info("Shutdown notification sent successfully")
        except grpc.RpcError as e:
            logging.error(f"gRPC error during shutdown notification: {e.code()} - {e.details()}")
        except Exception as e:
            logging.error(f"Unexpected error during shutdown notification: {e}")
        finally:
            # 关闭连接
            if self.channel:
                try:
                    self.channel.close()
                    logging.debug("gRPC channel closed")
                except Exception as e:
                    logging.error(f"Error closing gRPC channel: {e}")

# Global instance
grpc_manager = GrpcManager() 