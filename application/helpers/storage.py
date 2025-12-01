"""
S3/MinIO Storage Helper for generating presigned URLs.
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from application.helpers.logger import get_logger
import config

logger = get_logger("storage")


class S3Storage:
    """S3/MinIO storage client for file operations."""
    
    def __init__(self):
        """Initialize S3 client with configuration."""
        endpoint_url = f"http://{config.S3_HOST}:{config.S3_PORT}"
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            region_name='us-east-1'  # Required by boto3 but not used by MinIO
        )
        self.bucket_name = config.S3_BUCKET_NAME
        logger.info(f"S3Storage initialized :: Endpoint -> {endpoint_url} :: Bucket -> {self.bucket_name}")
    
    def generate_presigned_url(self, object_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for an S3 object.
        
        Args:
            object_key: S3 object key (file path in bucket)
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string or None if error occurs
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expiration
            )
            logger.debug(f"Generated presigned URL :: Key -> {object_key}")
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL :: Key -> {object_key} :: Error -> {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL :: Key -> {object_key} :: Error -> {str(e)}")
            return None
    
    def _generate_single_url(self, key: str, expiration: int) -> tuple[str, Optional[str]]:
        """Helper to generate single presigned URL."""
        if not key:
            return (key, None)
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return (key, url)
        except Exception as e:
            logger.error(f"Error generating presigned URL :: Key -> {key} :: Error -> {str(e)}")
            return (key, None)
    
    def generate_presigned_urls_batch(self, object_keys: list[str], expiration: int = 3600) -> dict[str, Optional[str]]:
        """
        Generate presigned URLs for multiple objects - PARALLEL OPTIMIZED.
        
        Args:
            object_keys: List of S3 object keys
            expiration: URL expiration time in seconds
            
        Returns:
            Dictionary mapping object keys to presigned URLs
        """
        if not object_keys:
            return {}
        
        result = {}
        
        # Use ThreadPoolExecutor for parallel URL generation
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._generate_single_url, key, expiration): key for key in object_keys}
            
            for future in as_completed(futures):
                try:
                    key, url = future.result()
                    result[key] = url
                except Exception as e:
                    original_key = futures[future]
                    logger.error(f"Failed to generate URL :: Key -> {original_key} :: Error -> {str(e)}")
                    result[original_key] = None
        
        return result


# Singleton instance
_storage_instance = None


def get_storage() -> S3Storage:
    """Get or create S3Storage singleton instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = S3Storage()
    return _storage_instance
