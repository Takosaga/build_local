import httpx
import config


class ERPNextError(Exception):
    pass


class ERPNextAdapter:
    def __init__(self):
        self.base_url = config.ERPNEXT_URL
        self.headers = {
            "Authorization": f"token {config.ERPNEXT_API_KEY}:{config.ERPNEXT_API_SECRET}",
            "Content-Type": "application/json",
        }

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{self.base_url}{endpoint}", headers=self.headers, params=params
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext GET {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def post(self, endpoint: str, data: dict) -> dict:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}{endpoint}", headers=self.headers, json=data
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext POST {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def put(self, endpoint: str, data: dict) -> dict:
        with httpx.Client(timeout=30.0) as client:
            resp = client.put(
                f"{self.base_url}{endpoint}", headers=self.headers, json=data
            )
        if not resp.is_success:
            raise ERPNextError(f"ERPNext PUT {endpoint} failed {resp.status_code}: {resp.text}")
        return resp.json()

    def is_reachable(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/method/ping")
            return resp.is_success
        except Exception:
            return False
