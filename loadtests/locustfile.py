from __future__ import annotations

from locust import HttpUser, between, task


class CommonUser(HttpUser):
    wait_time = between(1, 5)

    @task(10)
    def open_home(self) -> None:
        self.client.get("/", name="home")

    @task(2)
    def streamlit_health(self) -> None:
        self.client.get("/_stcore/health", name="streamlit_health")

    @task(1)
    def static_manifest(self) -> None:
        self.client.get("/manifest.json", name="manifest", catch_response=True)
