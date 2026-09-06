import requests


class ConfluenceClient:
    def __init__(self, base_url: str, pat: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api{path}"

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self.session.get(self._url(path), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict = None) -> dict:
        resp = self.session.post(self._url(path), json=json)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, json: dict = None) -> dict:
        resp = self.session.put(self._url(path), json=json)
        resp.raise_for_status()
        return resp.json()

    # -- Auth check --

    def current_user(self) -> dict:
        return self._get("/user/current")

    # -- Pages --

    def get_page(self, page_id: str, expand: str = "body.storage,version") -> dict:
        return self._get(f"/content/{page_id}", params={"expand": expand})

    def create_page(
        self, space_key: str, title: str, body_html: str, parent_id: str = None
    ) -> dict:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        return self._post("/content", json=payload)

    def update_page(
        self, page_id: str, title: str, body_html: str, version_number: int
    ) -> dict:
        payload = {
            "type": "page",
            "title": title,
            "version": {"number": version_number},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        return self._put(f"/content/{page_id}", json=payload)

    # -- Search --

    def search(self, cql: str, limit: int = 25) -> dict:
        return self._get("/content/search", params={"cql": cql, "limit": limit})
