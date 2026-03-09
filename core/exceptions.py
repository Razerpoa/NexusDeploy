from typing import Optional

class NexusError(Exception):
    """Base class for all NexusDeploy errors."""
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint

class AppNotFoundError(NexusError):
    """Raised when an application is not found."""
    pass

class ManifestError(NexusError):
    """Raised when there are issues with the manifest.yaml."""
    pass

class InfrastructureError(NexusError):
    """Raised when Docker or Nginx operations fail."""
    pass

class PortConflictError(NexusError):
    """Raised when a requested port is already in use."""
    pass
