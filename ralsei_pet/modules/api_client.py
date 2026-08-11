import requests
import json
import time
import logging
from typing import Dict, Any, Optional

class APIClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', 'https://api.doubao.com')
        self.model = config.get('model', 'doubao-pro')
        self.agent_id = config.get('agent_id', '')
        self.api_version = config.get('api_version', 'v1')
        self.timeout = config.get('timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 1.0)
        
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        self.logger = logging.getLogger('APIClient')
        self.logger.setLevel(logging.INFO)
        
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送API请求，包含重试逻辑"""
        if not self.enabled or not self.api_key:
            self.logger.warning("API客户端未启用或缺少API密钥")
            return None
        
        url = f"{self.base_url}/{self.api_version}/{endpoint}"
        
        for retry in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=data,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"API请求失败 (重试 {retry + 1}/{self.max_retries}): {e}")
                if retry < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("API请求达到最大重试次数，失败")
                    return None
    
    def get_commands(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从API获取控制命令"""
        endpoint = "agent/chat"
        data = {
            "model": self.model,
            "agent_id": self.agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False)
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        return self._make_request(endpoint, data)
    
    def send_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """向API发送Ralsei的状态信息"""
        endpoint = "agent/status"
        data = {
            "model": self.model,
            "agent_id": self.agent_id,
            "status": status
        }
        
        return self._make_request(endpoint, data)
    
    def execute_command(self, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """执行特定的API命令"""
        endpoint = "agent/execute"
        data = {
            "model": self.model,
            "agent_id": self.agent_id,
            "command": command
        }
        
        return self._make_request(endpoint, data)