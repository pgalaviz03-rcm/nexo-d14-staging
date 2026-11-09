"""Notification boundary for future authorized channels; never sends locally."""
from typing import Protocol
class AlertNotifier(Protocol):
    def notify(self,*,project_id:int,incident_id:int,snapshot_sha256:str,channel:str,idempotency_key:str)->str:...
class AlertDeliveryUnavailable(RuntimeError):pass
class DisabledAlertNotifier:
    def notify(self,**kwargs):raise AlertDeliveryUnavailable('alert_delivery_not_connected')
